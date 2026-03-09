import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { FaArrowUp, FaPlus } from 'react-icons/fa';
import './Chatbot.css';

const Chatbot = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    {
      sender: 'bot',
      type: 'text',
      content: 'Hi! I am your AI assistant. How can I help you today?',
    },
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const callFlaskAPI = async (message) => {
    try {
      const response = await axios.post('http://127.0.0.1:8000/chat', {
        message,
      });
      return response.data.reply;
    } catch (error) {
      console.error('FastAPI API error:', error.response?.data || error.message);
      return "Sorry, I'm having trouble right now.";
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = { sender: 'user', type: 'text', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const botReply = await callFlaskAPI(input);

    const botMessage = { sender: 'bot', type: 'text', content: botReply };
    setMessages((prev) => [...prev, botMessage]);
    setLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !loading) sendMessage();
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    const isImage = file.type.startsWith('image/');
    const userMessage = {
      sender: 'user',
      type: isImage ? 'image' : 'file',
      content: url,
      name: file.name,
    };

    const botMessage = {
      sender: 'bot',
      type: 'text',
      content: isImage
        ? 'Nice image! I currently only chat via text.'
        : `Thanks for the file "${file.name}"! I currently only chat via text.`,
    };

    setMessages((prev) => [...prev, userMessage, botMessage]);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  return (
    <div className="chatbot-page">
      <div className="chatbot-content">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.sender}`}>
            {msg.type === 'text' && <span>{msg.content}</span>}
            {msg.type === 'image' && (
              <img src={msg.content} alt="uploaded" className="chat-image" />
            )}
            {msg.type === 'file' && (
              <a
                href={msg.content}
                download={msg.name}
                target="_blank"
                rel="noopener noreferrer"
                className="chat-file"
              >
                📎 {msg.name}
              </a>
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-message bot">
            <em>Typing...</em>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chatbot-input">
        <label htmlFor="file-upload" className="file-upload-icon" title="Upload file">
          <FaPlus />
        </label>
        <input
          id="file-upload"
          type="file"
          onChange={handleFileUpload}
          style={{ display: 'none' }}
          disabled={loading}
        />

        <input
          type="text"
          placeholder={loading ? 'Waiting for response...' : 'Type a message...'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyPress}
          disabled={loading}
        />
        <button className="send-button" onClick={sendMessage} disabled={loading}>
          <FaArrowUp />
        </button>
      </div>
    </div>
  );
};

export default Chatbot;
