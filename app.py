import os
import json
import uuid
from flask import Flask, request, jsonify, send_from_directory, render_template, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'books.json')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme123')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def load_books():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_books(books):
    with open(DATA_FILE, 'w') as f:
        json.dump(books, f, indent=2)

# ── Public routes ──────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/books', methods=['GET'])
def get_books():
    books = load_books()
    genre = request.args.get('genre')
    year  = request.args.get('year')
    if genre:
        books = [b for b in books if b.get('genre', '').lower() == genre.lower()]
    if year:
        books = [b for b in books if str(b.get('year_read', '')) == year]
    return jsonify(books)

@app.route('/api/books/<book_id>', methods=['GET'])
def get_book(book_id):
    books = load_books()
    book = next((b for b in books if b['id'] == book_id), None)
    if not book:
        abort(404)
    return jsonify(book)

@app.route('/pdf/<filename>')
def serve_pdf(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ── Admin routes (password-protected) ────────────────────

def check_auth(req):
    pw = req.headers.get('X-Admin-Password') or req.form.get('password') or req.json and req.json.get('password')
    return pw == ADMIN_PASSWORD

@app.route('/api/books', methods=['POST'])
def add_book():
    if not check_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401

    title     = request.form.get('title', '').strip()
    author    = request.form.get('author', '').strip()
    genre     = request.form.get('genre', '').strip()
    year_read = request.form.get('year_read', '').strip()
    review    = request.form.get('review', '').strip()
    rating    = request.form.get('rating', '').strip()

    if not title or not author:
        return jsonify({'error': 'Title and author are required'}), 400

    pdf_filename = None
    if 'pdf' in request.files:
        f = request.files['pdf']
        if f and f.filename.lower().endswith('.pdf'):
            safe = secure_filename(f.filename)
            unique = f'{uuid.uuid4().hex}_{safe}'
            f.save(os.path.join(UPLOAD_FOLDER, unique))
            pdf_filename = unique

    books = load_books()
    book = {
        'id': uuid.uuid4().hex,
        'title': title,
        'author': author,
        'genre': genre,
        'year_read': int(year_read) if year_read.isdigit() else None,
        'review': review,
        'rating': int(rating) if rating.isdigit() and 1 <= int(rating) <= 5 else None,
        'pdf': pdf_filename,
    }
    books.append(book)
    save_books(books)
    return jsonify(book), 201

@app.route('/api/books/<book_id>', methods=['DELETE'])
def delete_book(book_id):
    if not check_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
    books = load_books()
    book = next((b for b in books if b['id'] == book_id), None)
    if not book:
        abort(404)
    if book.get('pdf'):
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, book['pdf']))
        except FileNotFoundError:
            pass
    books = [b for b in books if b['id'] != book_id]
    save_books(books)
    return jsonify({'deleted': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
