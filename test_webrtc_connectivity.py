# -*- coding: utf-8 -*-
"""Joins a real LiveKit room and reports how the media path was set up.

Signalling reaching the server proves very little on a phone's
connection - that runs over TCP 443 and almost always works. What
decides whether a call carries audio is whether ICE can find a media
path, and on a carrier's network (symmetric NAT) that path has to be
a relay.

This joins for real, publishes a track, and prints the candidate
pair that actually got used.
"""
import asyncio
import time

from livekit import api, rtc

from backend.microservices.livekit_Rag_services.core.config import settings


async def main() -> None:
    room_name = f"probe-{int(time.time())}"

    token = (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity("connectivity-probe")
        .with_name("probe")
        .with_grants(
            api.VideoGrants(room_join=True, room=room_name, can_publish=True)
        )
        .to_jwt()
    )

    room = rtc.Room()

    started = time.monotonic()

    try:
        await asyncio.wait_for(
            room.connect(settings.LIVEKIT_URL, token), timeout=30
        )
    except Exception as error:
        print(f"  CONNECT FAILED: {type(error).__name__}: {error}")
        return

    connect_ms = (time.monotonic() - started) * 1000
    print(f"  connected      : {connect_ms:.0f}ms  (room {room.name})")

    # Publishing is what actually forces a media path to be built -
    # signalling alone never leaves TCP 443.
    source = rtc.AudioSource(48000, 1)
    track = rtc.LocalAudioTrack.create_audio_track("probe", source)

    published = await room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )
    print(f"  track published: {published.sid}")

    # Send real frames for a few seconds so the path is exercised.
    frame_ms = 20
    samples = 48000 * frame_ms // 1000
    silence = bytearray(samples * 2)

    sent = 0
    for _ in range(int(3000 / frame_ms)):
        await source.capture_frame(
            rtc.AudioFrame(bytes(silence), 48000, 1, samples)
        )
        sent += 1
        await asyncio.sleep(frame_ms / 1000)

    print(f"  audio frames   : {sent} sent over 3s")

    stats = await room.get_rtc_stats()

    pair = None
    locals_, remotes = {}, {}

    # RtcStats holds the publisher's and subscriber's peer connections
    # separately; the outgoing audio lives on the publisher side.
    for entry in list(stats.publisher_stats) + list(stats.subscriber_stats):

        which = entry.WhichOneof("stats") if hasattr(entry, "WhichOneof") else None
        inner = getattr(entry, which, entry) if which else entry

        if which == "candidate_pair":
            data = getattr(inner, "candidate_pair", inner)
            if getattr(data, "nominated", False):
                pair = data
        elif which == "local_candidate":
            data = getattr(inner, "candidate", inner)
            locals_[getattr(inner, "id", "")] = data
        elif which == "remote_candidate":
            data = getattr(inner, "candidate", inner)
            remotes[getattr(inner, "id", "")] = data

    if pair is None:
        print("  media path     : no nominated candidate pair found")
    else:
        local = locals_.get(getattr(pair, "local_candidate_id", ""), None)
        remote = remotes.get(getattr(pair, "remote_candidate_id", ""), None)

        ltype = getattr(local, "candidate_type", "?")
        ltype = getattr(ltype, "value", ltype)
        proto = getattr(local, "protocol", "?")
        proto = getattr(proto, "value", proto)
        rtype = getattr(remote, "candidate_type", "?")
        rtype = getattr(rtype, "value", rtype)

        rtt = getattr(pair, "current_round_trip_time", None)

        print(f"  media path     : local={ltype}/{proto}  remote={rtype}")
        print(f"  bytes sent     : {getattr(pair, 'bytes_sent', 0)}")
        if rtt:
            print(f"  media rtt      : {rtt * 1000:.0f}ms")

        if ltype == "relay":
            print("  -> relayed through TURN, which is expected on a")
            print("     carrier network. Audio works; it costs latency.")
        elif ltype in ("srflx", "prflx", "host"):
            print("  -> direct path, no relay needed.")

    await room.disconnect()
    print("  disconnected   : clean")


if __name__ == "__main__":
    asyncio.run(main())
