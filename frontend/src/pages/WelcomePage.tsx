import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { CheckIcon } from '../components/Icons';
import { TrailArt } from '../components/TrailArt';
import { fr } from '../content/fr';
import { Mascot, type MascotHandle } from '../mascot/Mascot';

const t = fr.welcome;

export function WelcomePage() {
  const mascot = useRef<MascotHandle>(null);

  useEffect(() => mascot.current?.perform('greet', 'openArms'), []);

  return (
    <main className="welcome">
      <div className="welcome__art">
        <TrailArt />
        <Mascot ref={mascot} mood="idle" framing="full" className="mascot--welcome" />
      </div>
      <h1>{t.title}</h1>
      <p className="welcome__intro">{t.intro}</p>
      <ul className="promises">
        {t.promises.map((promise) => (
          <li key={promise}>
            <CheckIcon />
            {promise}
          </li>
        ))}
      </ul>
      <div className="welcome__actions">
        <Link to="/inscription" className="button button--primary">
          {t.start}
        </Link>
        <Link to="/connexion" className="text-link">
          {t.resume}
        </Link>
      </div>
    </main>
  );
}
