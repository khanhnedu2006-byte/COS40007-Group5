export default function AboutPage() {
  return (
    <main className="about-page" id="about-content">
      <div className="about-page-inner">
        <a className="about-back" href="#/">Back to signal explorer</a>
        <header className="about-page-heading">
          <span className="eyebrow">HANOI SIGNAL</span>
          <h1>About this project</h1>
        </header>
        <div className="about-sections">
          {["Overview", "Team", "Acknowledgements"].map((title, index) => (
            <section className="about-section" key={title} aria-labelledby={`about-section-${index}`}>
              <h2 id={`about-section-${index}`}>{title}</h2>
              {/* Content will be added later. */}
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}
