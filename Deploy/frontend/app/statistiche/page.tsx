'use client';

export default function StatistichePage() {
  return (
    <div className="dashboard-content min-h-screen flex justify-center items-center">
      <div className="content-card max-w-2xl w-full text-center py-12">
        <div className="mb-6">
          <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-[#286291] to-[#113357] mb-6">
            <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
        </div>
        <h2 className="text-3xl font-bold text-gray-800 mb-3">Statistiche</h2>
        <p className="text-lg text-gray-600 mb-2">Sezione in fase di sviluppo</p>
        <p className="text-sm text-gray-500">Stiamo lavorando per offrirti una visualizzazione completa delle statistiche e dei report.</p>
      </div>
    </div>
  );
}

