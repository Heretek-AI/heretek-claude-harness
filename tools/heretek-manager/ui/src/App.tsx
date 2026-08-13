import { useState, useEffect } from "react";

export default function App() {
  const [status, setStatus] = useState<{ status: string; version: string } | null>(null);

  useEffect(() => {
    fetch("/api/status")
      .then((r) => r.json())
      .then(setStatus)
      .catch(console.error);
  }, []);

  if (!status) return <div>Loading...</div>;

  return (
    <div>
      <h1>heretek-manager</h1>
      <p>Status: {status.status}</p>
      <p>Version: {status.version}</p>
    </div>
  );
}
