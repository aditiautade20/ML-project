/**
 * Utility for simple, descriptive due-date reminders.
 *
 * Requirements:
 * - "Due in 3 days", "Due today", or "Due date passed".
 * - If the due date is missing: "Due date not found".
 * - Never infer whether an invoice has been paid based on its due date.
 */
export function getDueDateReminder(dueDateStr) {
  if (!dueDateStr) {
    return {
      text: 'Due date not found',
      status: 'missing',
      badgeClass: 'bg-slate-100 text-slate-600 border-slate-200',
    };
  }

  const parts = String(dueDateStr).split('-');
  if (parts.length !== 3) {
    return {
      text: 'Due date not found',
      status: 'missing',
      badgeClass: 'bg-slate-100 text-slate-600 border-slate-200',
    };
  }

  const year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10) - 1;
  const day = parseInt(parts[2], 10);

  const due = new Date(year, month, day);
  if (isNaN(due.getTime())) {
    return {
      text: 'Due date not found',
      status: 'missing',
      badgeClass: 'bg-slate-100 text-slate-600 border-slate-200',
    };
  }

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  const diffTime = due.getTime() - today.getTime();
  const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return {
      text: 'Due today',
      status: 'today',
      days: 0,
      badgeClass: 'bg-amber-50 text-amber-800 border-amber-300 font-semibold',
    };
  } else if (diffDays > 0) {
    return {
      text: `Due in ${diffDays} day${diffDays === 1 ? '' : 's'}`,
      status: 'upcoming',
      days: diffDays,
      badgeClass: 'bg-sky-50 text-sky-800 border-sky-200',
    };
  } else {
    return {
      text: 'Due date passed',
      status: 'passed',
      days: Math.abs(diffDays),
      badgeClass: 'bg-rose-50 text-rose-800 border-rose-200',
    };
  }
}
