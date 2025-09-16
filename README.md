🚀 Stegano Studio Web 🕳️
=====================================================

Tagline: A Secure and Playful Steganography Studio for Web Applications

Description
-----------

Stegano Studio Web is a Python-based web application that enables developers to hide and extract sensitive information within images using steganography. This project aims to provide a user-friendly interface for encrypting, decrypting, and hiding data in images, making it a valuable tool for securing sensitive information and creative applications.

Features
--------

 1. 📁 Image Steganography

 Hide text, images, or files within images using various algorithms and techniques.
 Support for multiple image formats, including JPEG, PNG, and GIF.
 Advanced options for customizing steganography settings, such as payload size, compression, and encryption.

 2. 📊 Payload Generation

 Generate ZIP files containing multiple files and folders for hiding and encrypting.
 Support for various compression algorithms and encryption methods.

 3. 🔒 Encryption and Decryption

 Encrypt and decrypt payload files using AES-GCM and PBKDF2-HMAC algorithms.
 Support for password-based encryption and decryption.

 4. 🔍 Image Viewer

 Display images with hidden payloads, allowing users to view and extract the hidden data.
 Support for zooming, panning, and zooming in/out.

 5. 💻 Command-Line Interface

 Run stegano_core.py as a command-line tool for batch processing and automation.

 6. 📊 Statistics and Analytics

 Display statistics on payload size, compression ratio, and encryption/decryption performance.
 Generate reports on steganography success rates and failure modes.

 7. 🔧 Customization and Extensibility

 Support for custom plugins and extensions for adding new steganography algorithms and features.
 Allow users to create and share their own custom steganography tools.

 8. 📝 Documentation and Tutorials

 Comprehensive documentation and tutorials for getting started with Stegano Studio Web.
 Step-by-step guides for using the web application and command-line interface.

 9. 🌐 Web Interface

 A user-friendly web interface for hiding and extracting payloads, with real-time updates and feedback.
 Support for multiple browsers and devices.

 10. 📊 Performance Optimization

 Optimized for performance, with caching and compression enabled by default.
 Support for multiple CPU cores for parallel processing.

Tech Stack
-----------

| Component        | Version      | Description                                                          |
| ---------------- | ------------ | -------------------------------------------------------------------- |
| Frontend         | Tailwind CSS | CSS framework for styling and layout                                 |
| Backend          | Flask        | Python web framework for building the web application                |
| Tools            | Pillow       | Python imaging library for image processing                          |
| Algorithms       | AES-GCM      | Advanced encryption standard for encrypting payload files            |
| Hashing          | PBKDF2-HMAC  | Password-based key derivation function for encryption and decryption |
| File Compression | ZIP          | Compression algorithm for payload files                              |

Project Structure
---------------

 app.py: Main application file for the web interface  
 stegano_core.py: Core library for steganography algorithms and payload generation  
 style.css: CSS file for custom styling and layout  
 app.js: JavaScript file for client-side functionality and toast notifications  
 index.html: HTML file for the web interface  
 images: Directory for storing and serving images  
 payloads: Directory for storing and serving payload files  
 static: Directory for storing static files, such as CSS and JavaScript files  

How to Run
------------

⚙️ Local Installation

1. Clone repository:
```
    git clone https://github.com/Dhruv3215/stegano-studio.git
    cd stegano-studio
```

2. Create virtual environment & install dependencies:
```
    python -m venv venv
    source venv/bin/activate   # (Linux/Mac)
    venv\Scripts\activate      # (Windows)
```

3. Install dependencies:
```
   pip install -r requirements.txt
```

4. Run the Flask app:
```
   python app.py
``` 

6. Open browser:
```
   http://127.0.0.1:5000
```
 
🚀 Live Demo
   app will be accessible at: 
      👉🏻👉🏻👉🏻
      [`Stegano-Studio`](https://stegano-studio-1xdr.onrender.com/)
      👈🏻👈🏻👈🏻

API Reference
-------------

 /stegano: Endpoint for generating and hiding payloads  
 /payloads: Endpoint for downloading and extracting payloads  
 /images: Endpoint for displaying and processing images  

⚠️ Disclaimer
-------------

This project is created for educational purposes only.
It is not intended for illegal or malicious use.

The project is still under development 🛠️ — features and stability may change over time.

Author
-----

DHRUV PATEL

I hope this README.md meets your requirements! 😊
