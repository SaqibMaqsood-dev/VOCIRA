import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page-shell flex items-center justify-center">
      <div className="glass w-full max-w-md p-8 text-center">
        <p className="text-sm font-semibold tracking-wide text-text-secondary">
          404
        </p>
        <h1 className="mt-2 text-xl font-semibold text-text-primary">
          Page not found
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          The page you’re looking for doesn’t exist.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] px-5 py-3 text-sm font-semibold text-text-primary shadow-card"
        >
          Back to Home
        </Link>
      </div>
    </div>
  );
}

