"use client";

/**
 * Admin pages ka aana-jaana.
 *
 * Pehle animation sirf dashboard par thi (duration 0.4, y 10) aur
 * baqi teen pages par bilkul nahi. Is liye ek page narmi se aata
 * tha aur doosra jhatke se - aur dashboard par wapis aate hi wo
 * fade phir se chalta tha, jo jhilmilahat lagti thi.
 *
 * Ab ek hi jagah, sab ke liye:
 *
 *   - exit animation NAHI. Purana page fade out ho kar jaye to
 *     beech mein khali screen ka lamha aata hai - wahi "fade in
 *     aur out" wala jhatka tha. Naya page bas narmi se aa jata hai.
 *
 *   - y sirf 6px (pehle 10) - halki si harkat, uchhal nahi.
 *
 *   - duration 0.45s aur ease-out curve, taake shuru tez ho aur
 *     aakhir mein theher kar ruke. Linear ya easeOut se zyada narm
 *     mehsoos hota hai.
 *
 * key={pathname} se har page apni entry khud chalata hai.
 */

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";

export default function PageTransition({ children }) {
  const pathname = usePathname();

  return (
    <motion.div
      key={pathname}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.45,
        // easeOutQuint - shuru mein raftaar, aakhir mein narmi
        ease: [0.22, 1, 0.36, 1],
      }}
    >
      {children}
    </motion.div>
  );
}
