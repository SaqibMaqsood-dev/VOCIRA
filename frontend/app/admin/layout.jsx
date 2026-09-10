import AdminGuard from "@/app/admin/_components/AdminGuard";
import AdminLayout from "@/app/admin/_components/AdminLayout";

export default function AdminRootLayout({ children }) {
  // The guard sits outermost: not even the panel's frame renders
  // before the role is checked. Otherwise the wrong user caught a
  // glimpse of the sidebar and headings.
  return (
    <AdminGuard>
      <AdminLayout>{children}</AdminLayout>
    </AdminGuard>
  );
}
