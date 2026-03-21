const DEFAULT_METRICS = {
  processed: 0,
  sent: 0,
  failed: 0,
  invalid_rows: 0,
}

export default function StatusTable({ metrics }) {
  const merged = { ...DEFAULT_METRICS, ...(metrics || {}) }

  return (
    <table className="status-table">
      <thead>
        <tr>
          <th>Metric</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>processed</td>
          <td>{merged.processed}</td>
        </tr>
        <tr>
          <td>sent</td>
          <td>{merged.sent}</td>
        </tr>
        <tr>
          <td>failed</td>
          <td>{merged.failed}</td>
        </tr>
        <tr>
          <td>invalid_rows</td>
          <td>{merged.invalid_rows}</td>
        </tr>
      </tbody>
    </table>
  )
}
