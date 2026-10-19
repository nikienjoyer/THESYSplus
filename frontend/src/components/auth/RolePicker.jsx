/**
 * RolePicker — first screen of /request-access.
 *
 * Students and faculty sign up differently (students upload an ID, faculty
 * wait for an administrator), so the role is asked before any form.
 * Approved mockup: docs/superpowers/specs/mockups/2026-10-13-request-access-role-first.html
 */

import { ChevronRight, GraduationCap, Monitor } from 'lucide-react';

const ROLES = [
  { role: 'student', Icon: GraduationCap, title: 'Student', line: 'Student-number email and your Student ID or COR' },
  { role: 'faculty', Icon: Monitor, title: 'Faculty', line: 'PampangaStateU email. An administrator approves it.' },
];

export default function RolePicker({ onPick }) {
  return (
    <section aria-labelledby="role-picker-heading">
      <h2 id="role-picker-heading" className="text-xl font-bold text-ink">Who is requesting access?</h2>
      <p className="mt-1.5 text-sm text-body">Students and faculty sign up differently.</p>

      <div className="mt-6 overflow-hidden rounded-xl border border-border-strong bg-surface shadow-card">
        {ROLES.map(({ role, Icon, title, line }) => (
          <button key={role} type="button" onClick={() => onPick(role)}
            className="group grid w-full grid-cols-[auto_1fr_auto] items-center gap-3.5 px-4 py-4 text-left transition-colors
              [&+&]:border-t [&+&]:border-border-default hover:bg-primary-light
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary-light text-[color:var(--color-primary)]">
              <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
            </span>
            <span>
              <span className="block text-[15px] font-semibold text-ink">{title}</span>
              <span className="block text-[13px] leading-snug text-muted">{line}</span>
            </span>
            <ChevronRight className="h-[18px] w-[18px] text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-[color:var(--color-primary)]" aria-hidden="true" />
          </button>
        ))}
      </div>
    </section>
  );
}
