import { useState } from "react";

function App() {
  const [message, setMessage] = useState("");
  const [chat, setChat] = useState([]);

  const sendMessage = async () => {
    if (!message) return;

    setChat([...chat, { role: "user", text: message }]);
    setMessage("");

    const res = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    }); 

    const data = await res.json();
    setChat(prev => [
  ...prev,
  {
    role: "bot",
    text: typeof data.reply === "string" ? data.reply : data.reply
  }
]);

  };

  return (
    <div style={{ maxWidth: 500, margin: "40px auto" }}>
      <h2>GenAI Chatbot</h2>

      <div style={{ border: "1px solid #ccc", padding: 10, height: 300, overflowY: "auto" }}>
        {chat.map((c, i) => (
  <div key={i} style={{ display: "flex", justifyContent: c.role === "user" ? "flex-end" : "flex-start", marginBottom: 8 }}>
    <div style={{ maxWidth: "80%", padding: 10, borderRadius: 8, background: c.role === "user" ? "#DCF8C6" : "#EAEAEA" }}>
      
      {/* STRING RESPONSE */}
      {typeof c.text === "string" && <span>{c.text}</span>}

      {/* ARRAY RESPONSE (TABLE) */}
      {Array.isArray(c.text) && (
        <table border="1" cellPadding="5">
          <thead>
            <tr>
              <th>Ticket ID</th>
              <th>Company</th>
              <th>Status</th>
              <th>Created Date</th>
            </tr>
          </thead>
          <tbody>
            {c.text.map((row, idx) => (
              <tr key={idx}>
                <td>{row.ticket_id}</td>
                <td>{row.company}</td>
                <td>{row.status}</td>
                <td>{row.created_date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

    </div>
  </div>
))}


      </div>

      <input
        value={message}
        onChange={e => setMessage(e.target.value)}
        placeholder="Type a message..."
        style={{ width: "80%" }}
      />
      <button onClick={sendMessage}>Send</button>
    </div>
  );
}

export default App;
