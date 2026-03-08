import React, { useState } from 'react';

type Reference = {
  title: string;
  author: string;
  doi: string;
};

type MangaPage = {
  imageUrl: string;
  pageNumber: number;
};

const mangaPages: MangaPage[] = [
  { imageUrl: 'https://dummyimage.com/600x900/ebf5fb/333&text=1', pageNumber: 1 },
  { imageUrl: 'https://dummyimage.com/600x900/d6eaf8/333&text=2', pageNumber: 2 },
  { imageUrl: 'https://dummyimage.com/600x900/aed6f1/333&text=3', pageNumber: 3 },
];

const references: Reference[] = [
  {
    title: "Quantum Entanglement and Information",
    author: "A. Einstein, B. Podolsky, N. Rosen",
    doi: "10.1103/PhysRev.47.777"
  },
  {
    title: "A New Kind of Science",
    author: "Stephen Wolfram",
    doi: "10.5555/nks.123456"
  }
];

const DoctorCanvas: React.FC = () => {
  const [currentPage, setCurrentPage] = useState(0);

  const nextPage = () => {
    setCurrentPage((prev) =>
      prev < mangaPages.length - 1 ? prev + 1 : prev
    );
  };

  const prevPage = () => {
    setCurrentPage((prev) =>
      prev > 0 ? prev - 1 : prev
    );
  };

  return (
    <div style={{
      display: 'flex',
      minHeight: '100vh',
      background: 'linear-gradient(90deg, #e6f0fa 70%, #192841 100%)',
      fontFamily: 'Inter, "Helvetica Neue", Arial, sans-serif'
    }}>
      {/* Manga Viewer */}
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
      }}>
        <button
          aria-label="前のページ"
          onClick={prevPage}
          disabled={currentPage === 0}
          style={{
            background: 'none',
            border: 'none',
            color: '#3f51b5',
            fontSize: '2rem',
            cursor: currentPage === 0 ? 'not-allowed' : 'pointer',
            opacity: currentPage === 0 ? 0.3 : 1,
            marginRight: '1.5rem'
          }}
        >
          ‹
        </button>
        <img
          src={mangaPages[currentPage].imageUrl}
          alt={`Manga Page ${currentPage + 1}`}
          style={{
            boxShadow: '0 6px 32px 0 rgba(25,40,65,.23)',
            borderRadius: '1rem',
            border: '2px solid #b2bec3',
            maxWidth: '420px',
            width: '100%',
            height: 'auto',
            background: '#fff',
            transition: 'box-shadow 0.2s'
          }}
        />
        <button
          aria-label="次のページ"
          onClick={nextPage}
          disabled={currentPage >= mangaPages.length - 1}
          style={{
            background: 'none',
            border: 'none',
            color: '#3f51b5',
            fontSize: '2rem',
            cursor: currentPage >= mangaPages.length - 1 ? 'not-allowed' : 'pointer',
            opacity: currentPage >= mangaPages.length - 1 ? 0.3 : 1,
            marginLeft: '1.5rem'
          }}
        >
          ›
        </button>
      </div>

      {/* Sidebar: References */}
      <aside style={{
        width: '340px',
        background: '#253358EF',
        color: '#f2f6fa',
        padding: '2.5rem 2rem',
        boxShadow: '-1px 0 8px 0 rgba(25,40,65,.04)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-start',
        borderTopLeftRadius: '1.5rem',
        borderBottomLeftRadius: '1.5rem'
      }}>
        <h2 style={{
          fontSize: '1.3rem',
          letterSpacing: '0.04em',
          marginBottom: '1.2rem',
          fontWeight: 700,
          color: '#ffe03a'
        }}>
          📚 論文出典 (References)
        </h2>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {references.map((ref, i) => (
            <li
              key={ref.doi}
              style={{
                marginBottom: '1.3rem',
                background: i % 2 === 0 ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.10)',
                borderRadius: '10px',
                padding: '0.8rem 1rem',
                transition: 'background 0.2s',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '1.05rem', marginBottom: '0.1em', color: '#dbeafe' }}>
                {ref.title}
              </div>
              <div style={{ fontSize: '0.96rem', color: '#d2ceee', marginBottom: '0.2em' }}>
                <span style={{ fontWeight: 450 }}>{ref.author}</span>
              </div>
              <div style={{ fontSize: '0.91rem' }}>
                <a
                  href={`https://doi.org/${ref.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#91d6fe', textDecoration: 'underline dotted' }}
                >
                  DOI: {ref.doi}
                </a>
              </div>
            </li>
          ))}
        </ul>
        <footer style={{ marginTop: 'auto', fontSize: '13px', color: '#b2bec3', paddingTop: '1.3rem' }}>
          <span style={{ color: '#ccffff' }}>Quantumy Doctor Canvas</span> (Phase 1)
        </footer>
      </aside>
    </div>
  );
};


export default DoctorCanvas;