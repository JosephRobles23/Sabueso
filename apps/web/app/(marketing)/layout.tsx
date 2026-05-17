import { Nav } from "@/components/nav";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav variant="marketing" />
      {children}
    </>
  );
}
