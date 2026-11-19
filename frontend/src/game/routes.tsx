import { lazy, Suspense, type ReactNode } from 'react';
import { Loading } from '../components/Feedback';

const QuizPage = lazy(() => import('./quiz/QuizPage'));
const GamesHubPage = lazy(() => import('./hub/GamesHubPage'));
const PlayPage = lazy(() => import('./play/PlayPage'));
const SheetPage = lazy(() => import('./sheet/SheetPage'));
const YouthGamePanel = lazy(() => import('./backoffice/YouthGamePanel'));

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Loading />}>{children}</Suspense>;
}

export const QuizRoute = () => <Lazy><QuizPage /></Lazy>;
export const GamesHubRoute = () => <Lazy><GamesHubPage /></Lazy>;
export const PlayRoute = () => <Lazy><PlayPage /></Lazy>;
export const SheetRoute = () => <Lazy><SheetPage /></Lazy>;
export const YouthGameRoute = ({ youthId }: { youthId: string }) => (
  <Lazy><YouthGamePanel youthId={youthId} /></Lazy>
);
