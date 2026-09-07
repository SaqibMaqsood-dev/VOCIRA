import AdminGuard from "@/app/admin/_components/AdminGuard";
import AdminLayout from "@/app/admin/_components/AdminLayout";

export default function AdminRootLayout({ children }) {
  // Guard sab se bahar: role dekhne se pehle panel ka dhaancha bhi
  // render nahi hota. Warna ghalat user ko sidebar aur headings ki
  // jhalak dikh jati thi.
  return (
    <AdminGuard>
      <AdminLayout>{children}</AdminLayout>
    </AdminGuard>
  );
}
