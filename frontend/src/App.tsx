import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { HomeRedirect, PublicOnly, RequireRole } from './auth/guards';
import { ThemeToggle } from './components/ThemeToggle';
import { fr } from './content/fr';
import { OnboardingGate } from './game/OnboardingGate';
import { GamesHubRoute, PlayRoute, QuizRoute, SheetRoute } from './game/routes';
import { BackofficeLayout } from './layouts/BackofficeLayout';
import { YouthLayout } from './layouts/YouthLayout';
import { AuthPage } from './pages/AuthPage';
import { WelcomePage } from './pages/WelcomePage';
import { YouthDetailPage } from './pages/backoffice/YouthDetailPage';
import { YouthListPage } from './pages/backoffice/YouthListPage';
import { ChatPage } from './pages/youth/ChatPage';
import { MapPage } from './pages/youth/MapPage';
import { MePage } from './pages/youth/MePage';

export function App() {
  return (
    <AuthProvider>
      <ThemeToggle />
      <BrowserRouter>
        <Routes>
          <Route index element={<HomeRedirect />} />

          <Route element={<PublicOnly />}>
            <Route path="bienvenue" element={<WelcomePage />} />
            <Route path="connexion" element={<AuthPage mode="login" />} />
            <Route path="inscription" element={<AuthPage mode="register" />} />
          </Route>

          <Route element={<RequireRole roles={['youth']} />}>
            {/* Plein écran, sans la barre de navigation. */}
            <Route path="jeune/quiz" element={<QuizRoute />} />
            <Route path="jeune/jeux/:instrumentId" element={<PlayRoute />} />
            <Route element={<OnboardingGate />}>
              <Route path="jeune" element={<YouthLayout />}>
                <Route index element={<Navigate to="discussion" replace />} />
                <Route path="discussion" element={<ChatPage />} />
                <Route path="carte" element={<MapPage />} />
                <Route path="competences" element={<Navigate to="/jeune/carte" replace />} />
                <Route path="jeux" element={<GamesHubRoute />} />
                <Route path="fiche" element={<SheetRoute />} />
                <Route path="moi" element={<MePage />} />
              </Route>
            </Route>
          </Route>

          <Route element={<RequireRole roles={['psychologist', 'admin']} />}>
            <Route path="psy" element={<BackofficeLayout />}>
              <Route index element={<Navigate to="jeunes" replace />} />
              <Route path="jeunes" element={<YouthListPage />} />
              <Route path="jeunes/:youthId" element={<YouthDetailPage />} />
            </Route>
          </Route>

          <Route path="*" element={<p className="state">{fr.notFound}</p>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
