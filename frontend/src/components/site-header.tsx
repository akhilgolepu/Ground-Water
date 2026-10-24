import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";

const links = [
  { href: "#network", label: "Network" },
  { href: "#wells", label: "Wells" },
  { href: "#evidence", label: "Evidence" },
  { href: "#agenda", label: "Research agenda" },
];

export function SiteHeader() {
  const { theme, toggle } = useTheme();
  return (
    <header className="sticky top-0 z-30 border-b border-rule bg-ground/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-6 px-4 sm:px-6">
        <a href="#top" className="type-heading flex items-center gap-2 text-[1.05rem] text-ink">
          <svg aria-hidden viewBox="0 0 20 20" className="h-5 w-5">
            <rect x="1" y="5" width="18" height="2" fill="var(--soil)" />
            <path d="M10 8v8" stroke="var(--s1)" strokeWidth="2" strokeLinecap="round" />
            <circle cx="10" cy="16" r="2.4" fill="var(--s1)" />
          </svg>
          AquaSense
        </a>
        <nav
          aria-label="Sections"
          className="ml-auto hidden items-center gap-5 text-[0.9375rem] text-ink-2 md:flex"
        >
          {links.map((l) => (
            <a key={l.href} href={l.href} className="hover:text-ink">
              {l.label}
            </a>
          ))}
        </nav>
        <button
          type="button"
          onClick={toggle}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded-md border border-rule text-ink-2 hover:text-ink md:ml-0"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  );
}
