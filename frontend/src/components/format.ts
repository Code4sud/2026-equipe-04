const dateTime = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });

export function formatDateTime(value: string): string {
  return dateTime.format(new Date(value));
}
