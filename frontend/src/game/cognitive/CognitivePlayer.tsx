import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { gameApi } from '../api';
import { NinjaContext, useNinjaState } from '../ninja';
import type { PublicInstrument, RunPayload, RunResult } from '../types';
import './cognitive.css';
import { cogFr } from './cognitive.fr';
import { CorsiGame } from './corsi/CorsiGame';
import { DigitsGame } from './digits/DigitsGame';
import { LogicGame } from './logic/LogicGame';
import { ResultScreen } from './ResultScreen';
import { keepRecord, summarize } from './results';
import { readSettings, type GameSettings } from './settings';
import { StroopGame } from './stroop/StroopGame';
import { GAMES_PATH, GameTop, NeoSays } from './ui';

const t = cogFr.common;

interface Outcome {
  result: RunResult;
  record: 'new' | 'first' | null;
}

function Game({
  instrument,
  settings,
  onFinish,
}: {
  instrument: PublicInstrument;
  settings: GameSettings;
  onFinish: (trials: unknown[]) => void;
}) {
  switch (settings.kind) {
    case 'corsi':
      return <CorsiGame instrument={instrument} settings={settings} onFinish={onFinish} />;
    case 'digits':
      return <DigitsGame instrument={instrument} settings={settings} onFinish={onFinish} />;
    case 'stroop':
      return <StroopGame instrument={instrument} settings={settings} onFinish={onFinish} />;
    case 'logic':
      return <LogicGame instrument={instrument} settings={settings} onFinish={onFinish} />;
  }
}

function Sending({ title, error, onRetry }: { title: string; error: string | null; onRetry: () => void }) {
  return (
    <section className="cog-intro cog-go">
      <GameTop title={title} />
      <NeoSays mood={error ? 'happy' : 'thinking'} big>
        {error ? t.sendError : t.sending}
      </NeoSays>
      {error && (
        <>
          <p className="form-error" role="alert">
            {error}
          </p>
          <button type="button" className="button button--primary cog-wide" onClick={onRetry}>
            {t.retrySend}
          </button>
        </>
      )}
    </section>
  );
}

/**
 * Jeux chronométrés (kind « performance ») : choisit le jeu d'après `scorer` et `variant`,
 * envoie tous les essais à la fin, puis montre le bilan calculé par le serveur.
 */
export function CognitivePlayer({ instrumentId }: { instrumentId: string }) {
  const { user } = useAuth();
  const [payload, setPayload] = useState<RunPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [trials, setTrials] = useState<unknown[] | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  /** Mode ninja (démo) : le jeu se joue tout seul jusqu'au bilan. */
  const ninja = useNinjaState();
  const stopNinja = ninja.stop;

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const next = await gameApi.startRun(instrumentId);
      setPayload(next);
      setTrials(null);
      setSendError(null);
      setOutcome(null);
    } catch (caught) {
      setLoadError(errorMessage(caught));
    }
  }, [instrumentId]);

  useEffect(() => {
    void load();
  }, [load]);

  const settings = useMemo(() => (payload ? readSettings(payload.instrument) : null), [payload]);

  const send = useCallback(
    async (list: unknown[]) => {
      if (!payload || !settings) return;
      // La partie est jouée : le mode ninja s'arrête sur le bilan.
      stopNinja();
      setTrials(list);
      setSendError(null);
      try {
        const result = await gameApi.completeRun(payload.run.id, list);
        const summary = summarize(settings, result.metrics);
        setOutcome({ result, record: user ? keepRecord(user.id, instrumentId, summary.score) : null });
      } catch (caught) {
        setSendError(errorMessage(caught));
      }
    },
    [payload, settings, user, instrumentId, stopNinja],
  );

  let screen;
  if (loadError) {
    screen = <ErrorState message={loadError} onRetry={() => void load()} />;
  } else if (!payload) {
    screen = <Loading />;
  } else if (!settings) {
    screen = (
      <section className="cog-intro">
        <GameTop title={payload.instrument.title} />
        <NeoSays mood="happy" big>
          {t.unsupported}
        </NeoSays>
        <Link className="button cog-wide" to={GAMES_PATH}>
          {t.back}
        </Link>
      </section>
    );
  } else if (outcome) {
    screen = (
      <ResultScreen
        instrument={payload.instrument}
        result={outcome.result}
        summary={summarize(settings, outcome.result.metrics)}
        record={outcome.record}
        onReplay={() => void load()}
      />
    );
  } else if (trials) {
    screen = <Sending title={payload.instrument.title} error={sendError} onRetry={() => void send(trials)} />;
  } else {
    screen = (
      <Game key={payload.run.id} instrument={payload.instrument} settings={settings} onFinish={send} />
    );
  }
  return (
    <NinjaContext.Provider value={ninja}>
      <div className="cog-screen" data-game={settings?.kind}>
        {screen}
      </div>
    </NinjaContext.Provider>
  );
}
