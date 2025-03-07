import { useEffect, useState } from 'react';
import styles from '../styles/Form.module.css';
import Head from 'next/head';

// Declare the intlTelInput function on the window object
interface IntlTelInput {
  destroy: () => void;
}

declare global {
  interface Window {
    intlTelInput: (
      input: HTMLInputElement,
      options: {
        utilsScript: string;
        initialCountry: string;
        geoIpLookup: (callback: (countryCode: string) => void) => void;
      }
    ) => IntlTelInput;
  }
}

export default function Home() {
  const [message, setMessage] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  // Initialize intl-tel-input when the component mounts
  useEffect(() => {
    const input = document.querySelector('#phone') as HTMLInputElement;
    if (input && typeof window !== 'undefined' && typeof window.intlTelInput !== 'undefined') {
      const iti = window.intlTelInput(input, {
        utilsScript: 'https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/utils.js',
        initialCountry: 'auto',
        geoIpLookup: (callback: (countryCode: string) => void) => {
          fetch('https://ipapi.co/json/')
            .then((res) => res.json())
            .then((data) => callback(data.country_code))
            .catch(() => callback('us'));
        },
      });

      // Cleanup on unmount
      return () => {
        iti.destroy();
      };
    } else if (!window.intlTelInput) {
      console.warn('intlTelInput is not available. Ensure the script loaded correctly.');
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const form = e.currentTarget;
    const name = (form.elements.namedItem('name') as HTMLInputElement).value;
    const email = (form.elements.namedItem('email') as HTMLInputElement).value;
    const phone = (form.elements.namedItem('phone') as HTMLInputElement).value;
    const cv = (form.elements.namedItem('cv') as HTMLInputElement).files?.[0];

    // Client-side validation
    if (!name || !email || !phone || !cv) {
      setMessage('Please fill in all fields');
      return;
    }

    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    if (!cv || !allowedTypes.includes(cv.type)) {
      setMessage('Please upload a PDF or DOCX file');
      return;
    }

    // Submit form data to the API route
    const formData = new FormData();
    formData.append('name', name);
    formData.append('email', email);
    formData.append('phone', phone);
    formData.append('cv', cv);

    try {
      setLoading(true);
      const response = await fetch('/api/submit', {
        method: 'POST',
        body: formData,
      });
      if (response.ok) {
        setLoading(false);
        setMessage('Application submitted successfully!');
        form.reset();
      } else {
        setLoading(false);
        setMessage('Error submitting application.');
      }
    } catch {
      setLoading(false);
      setMessage('Error submitting application.');
    }
  };

  return (
    <>
      <Head>
        <title>Job Application Form</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <link
          rel="stylesheet"
          href="https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/css/intlTelInput.css"
        />
        <script
          src="https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/intlTelInput.min.js"
          defer
        />
      </Head>
      <div className={styles.formContainer}>
      {loading && (
        <div className={styles.loadingOverlay}>
          <div className={styles.spinner}></div>
          <p>Submitting...</p>
        </div>
      )}

        <h1 className={styles.formTitle}>Job Application Form</h1>
        <form id="applicationForm" onSubmit={handleSubmit} encType="multipart/form-data">
          <div className={styles.formGroup}>
            <label htmlFor="name">Full Name:</label>
            <input
              type="text"
              id="name"
              name="name"
              required
              placeholder="John Doe"
            />
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="email">Email:</label>
            <input
              type="email"
              id="email"
              name="email"
              required
              placeholder="john@example.com"
            />
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="phone">Phone Number:</label>
            <input type="tel" id="phone" name="phone" required pattern="[0-9\+]*"/>
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="cv">Upload CV (PDF only):</label>
            <input type="file" id="cv" name="cv" accept=".pdf" required />
          </div>

          <button type="submit" className={styles.submitBtn}>
            Submit Application
          </button>
        </form>
        {message && <p className={styles.message}>{message}</p>}
      </div>
    </>
  );
}