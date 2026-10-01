// How a school reaches Vocira - the Contact us button on Vocira's own site.
export const VOCIRA_WHATSAPP = "+92 326 4368107";

// wa.me opens WhatsApp itself (the app on a phone, WhatsApp Web on a
// computer) with the chat to this number, the first line already written.
export const VOCIRA_WHATSAPP_URL =
  `https://wa.me/${VOCIRA_WHATSAPP.replace(/\D/g, "")}` +
  `?text=${encodeURIComponent("Hi Vocira, I would like to know more about Vocira for my school.")}`;
