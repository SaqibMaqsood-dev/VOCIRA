import AdminGuard from "@/app/admin/_components/AdminGuard";
import AdminLayout from "@/app/admin/_components/AdminLayout";
import { SUPER_ADMIN_ITEMS } from "@/app/admin/_components/Sidebar";

// The platform super admin's panel: every school, and adding or
// removing schools. A school's admin is sent back to /admin.
export default function SuperAdminRootLayout({ children }) {
  return (
    <AdminGuard allow="super_admin">
      <AdminLayout
        items={SUPER_ADMIN_ITEMS}
        title="Vocira Platform"
        home="/superadmin/schools"
        showPending={false}
        incomingCalls={false}
      >
        {children}
      </AdminLayout>
    </AdminGuard>
  );
}
