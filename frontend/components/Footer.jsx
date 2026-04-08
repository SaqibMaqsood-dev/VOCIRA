export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-white/10">
      <div className="mx-auto flex h-12 max-w-6xl flex-col items-center justify-center gap-1 px-4 text-xs md:h-10 md:flex-row md:justify-between">
        <p className="leading-none text-text-secondary">Copyright © {year}</p>
        <p className="leading-none text-text-secondary">Made by Trinova</p>
      </div>
    </footer>
  );
}

