export default function Footer() {
  const year = new Date().getFullYear();

  return (
    // pb clears the fixed tab bar on small screens - without it the
    // bar sits on top of this text. It also stacks to one centred
    // line there: two separate rows of grey text just above the bar
    // read as clutter on a phone, where a footer is a footnote
    // rather than a section.
    <footer className="border-t border-white/10 pb-24 lg:pb-0">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-center gap-x-2 gap-y-0.5 px-4 py-3 text-[11px] sm:flex-row sm:text-xs md:justify-between md:py-0 md:h-10">
        <p className="leading-none text-text-secondary">
          Copyright © {year}
        </p>

        <span
          aria-hidden="true"
          className="hidden text-text-secondary/40 sm:inline md:hidden"
        >
          ·
        </span>

        <p className="leading-none text-text-secondary">Made by Trinova</p>
      </div>
    </footer>
  );
}
