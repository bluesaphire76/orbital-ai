import Link from "next/link";

const navigation = [
  {
    href: "/",
    label: "Dashboard",
  },
  {
    href: "/catalog",
    label: "Orbital Catalog",
  },
  {
    href: "/conjunctions",
    label: "Conjunctions",
  },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brandMark">O</div>

        <div className="brandText">
          <strong>OrbitalAI</strong>
          <span>Orbital Intelligence</span>
        </div>
      </div>

      <nav className="navigation">
        {navigation.map((item) => (
          <Link
            className="navItem"
            href={item.href}
            key={item.href}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="sidebarFooter">
        Local-first platform
      </div>
    </aside>
  );
}
