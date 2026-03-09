import React from 'react';

const Contact = () => {
  return (
    <div
      className="contact-page"
      style={{
        maxWidth: '800px',
        margin: '90px auto 2rem',
        padding: '2rem',
        textAlign: 'center',
        fontSize: '1.2rem',
        lineHeight: '1.8'
      }}
    >
      <h2>Contact Me</h2>
      <p>Feel free to reach out!</p>
      <p>Email: <strong>gmail.com</strong></p>
      <p>LinkedIn: <strong>linkedin.com</strong></p>
      <p>GitHub: <strong>github.com</strong></p>
    </div>
  );
};

export default Contact;
