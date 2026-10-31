import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { WorkstationShell } from './layouts/WorkstationShell';
import { CommandCentrePage } from './pages/CommandCentrePage';
import { NetworkExplorerPage } from './pages/NetworkExplorerPage';
import { InvestigationWorkspacePage } from './pages/InvestigationWorkspacePage';
import { TransactionIntelligencePage } from './pages/TransactionIntelligencePage';
import { CasesPage } from './pages/CasesPage';
import { DataManagementPage } from './pages/DataManagementPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<WorkstationShell />}>
          <Route path="/" element={<CommandCentrePage />} />
          <Route path="/network" element={<NetworkExplorerPage />} />
          <Route path="/investigations" element={<InvestigationWorkspacePage />} />
          <Route path="/transactions" element={<TransactionIntelligencePage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/data" element={<DataManagementPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;

