const dateTime = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });
const day = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' });

export function formatDateTime(value: string): string {
  return dateTime.format(new Date(value));
}

export function formatDay(value: string): string {
  return day.format(new Date(value));
}
