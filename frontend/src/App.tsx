import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { HomeRedirect, PublicOnly, RequireRole } from './auth/guards';
import { fr } from './content/fr';
import { BackofficeLayout } from './layouts/BackofficeLayout';
import { YouthLayout } from './layouts/YouthLayout';
import { AuthPage } from './pages/AuthPage';
import { YouthDetailPage } from './pages/backoffice/YouthDetailPage';
import { YouthListPage } from './pages/backoffice/YouthListPage';
import { ChatPage } from './pages/youth/ChatPage';
import { SkillsPage } from './pages/youth/SkillsPage';

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route index element={<HomeRedirect />} />

          <Route element={<PublicOnly />}>
            <Route path="connexion" element={<AuthPage mode="login" />} />
            <Route path="inscription" element={<AuthPage mode="register" />} />
          </Route>

          <Route element={<RequireRole roles={['youth']} />}>
            <Route path="jeune" element={<YouthLayout />}>
              <Route index element={<Navigate to="discussion" replace />} />
              <Route path="discussion" element={<ChatPage />} />
              <Route path="competences" element={<SkillsPage />} />
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
