export default function SectionCard({ title, description, children }) {
  return (
    <section className="section-card">
      <header className="section-card-header">
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </header>
      <div className="section-card-content">{children}</div>
    </section>
  )
}
