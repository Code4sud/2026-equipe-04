import type { SafetyInfo } from '../api/types';
import { fr } from '../content/fr';

function formatPhone(contact: string): string {
  return contact.length === 10 ? contact.replace(/^(\d)(\d{3})(\d{3})(\d{3})$/, '$1 $2 $3 $4') : contact;
}

export function SafetyCard({ info }: { info: SafetyInfo }) {
  return (
    <aside className="safety" aria-label={info.message}>
      <p className="safety__message">{info.message}</p>
      <ul className="safety__list">
        {info.resources.map((resource) => (
          <li key={resource.contact} className="safety__item">
            <div>
              <strong>{resource.nom}</strong>
              <span className="muted">{resource.description}</span>
            </div>
            <a className="button button--small" href={`tel:${resource.contact}`}>
              {fr.chat.safetyCall} {formatPhone(resource.contact)}
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
