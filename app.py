from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os

BASE_DIR = os.path.abspath(os.path.dirname(__name__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + os.path.join(BASE_DIR, "instance", "tracker.sqlite")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "991e7c1fc8d87d34f52bf8b3"

os.makedirs(os.path.join(BASE_DIR,"instance"), exist_ok=True)

db = SQLAlchemy(app)

#Models

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    client_type = db.Column(db.String(50), nullable=False)
    documents = db.relationship('ClientDocument', backref='client', cascade='all, delete-orphan')

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_type = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(300), nullable=False)

class ClientDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    name = db.Column(db.String(200), nullable=True)
    received = db.Column(db.Boolean, default=False)
    document = db.relationship('Document')

DEFAULT_TYPES = ['Proprietorship','Partnership','LLP','Pvt Ltd','Salaried']

DEFAULT_DOCS = {
    'Proprietorship': [
        'Aadhaar', 'PAN', 'GST Certificate', 'Udyam',
        'Bank Statement (12 months)', 'ITR (2 years)', 'Ownership Proof', 'GST 3B',
        'House Address Proof', 'Office Address Proof'
    ],
    'Partnership': [
        'Partnership Deed', "PAN of Firm", 'GST Certificate', 'Address Proof of Firm',
        "Partners' Aadhaar & PAN", 'Bank Statement (12 months)', 'ITR (2 years)', 'GST 3B', 'Udyam'
    ],
    'LLP': [
        'LLP Agreement', 'PAN of LLP', 'Certificate of Incorporation', 'GST Certificate',
        'Address Proof of LLP', "Partners' Aadhaar & PAN", 'Bank Statement (12 months)', 'ITR (2 years)'
    ],
    'Pvt Ltd': [
        'MOA & AOA', 'Certificate of Incorporation', 'Company PAN', 'GST Certificate',
        "Directors' Aadhaar & PAN", 'Board Resolution for Loan', 'Bank Statement (12 months)', 'ITR (2 years)'
    ],
    'Salaried': [
        'Aadhaar', 'PAN', 'Salary Slips (3 months)', 'Bank Statement (6 months)', 'Form 16',
        'Offer/Appointment Letter', 'Company ID Card'
    ]
}

#Routes

@app.route('/')
def index():
    clients = Client.query.order_by(Client.name).all()
    return render_template('index.html', clients=clients)


#add client from first page
@app.route('/add', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        client_type = request.form.get('client_type')
        if not name:
            flash('Client name required', 'danger')
            return redirect(url_for('add_client'))
        client = Client(name=name, client_type=client_type)
        db.session.add(client)
        db.session.commit()
    # attach default documents for this type
        docs = Document.query.filter_by(client_type=client_type).all()
        for d in docs:
            cd = ClientDocument(client_id=client.id, document_id=d.id, name=d.name, received=False)
            db.session.add(cd)
        db.session.commit()
        flash('Client added', 'success')
        return redirect(url_for('index'))
    types = DEFAULT_TYPES
    return render_template('add_client.html', types=types)



#delete clients from index.html
@app.route('/delete_client/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    client = Client.query.get_or_404(client_id)
    # Delete all linked client documents
    for cd in client.documents:
        db.session.delete(cd)
    db.session.delete(client)
    db.session.commit()
    flash("Client deleted successfully!", "success")
    return redirect(url_for('index'))



#Shows the client details
@app.route('/client/<int:client_id>', methods=['GET','POST'])
def client_detail(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        # update received status for each client_document
        for cd in client.documents:
        # checkbox name: received-<cd.id>
            val = request.form.get(f'received-{cd.id}')
            cd.received = True if val == 'on' else False
        db.session.commit()
        flash('Updated document statuses', 'success')
        return redirect(url_for('client_detail', client_id=client_id))
    docs = sorted(client.documents, key=lambda x: x.document.name.lower() if x.document else x.name.lower())
    return render_template('client_detail.html', client=client, docs=docs)



#edit documents for the client
@app.route('/edit_documents/<int:client_id>', methods=['GET','POST'])
def edit_documents(client_id):
    client = Client.query.get_or_404(client_id)
        # Add a new custom document for this client (ad-hoc)
    new_doc_name = request.form.get('new_doc', '').strip()
    if new_doc_name:
        # Create a Document entry under the client's type (this will become available for future clients of same type)
            # attach to the client
        cd = ClientDocument(client_id=client.id, document_id=None, name=new_doc_name, received=False)
        db.session.add(cd)
        db.session.commit()
        flash('Added document', 'success')
    return redirect(url_for('client_detail', client_id=client_id))



#Delete documents from the client detail
@app.route('/delete_document/<int:cd_id>/<int:client_id>', methods=['POST'])
def delete_document(cd_id, client_id):
    cd = ClientDocument.query.get_or_404(cd_id)

    db.session.delete(cd)
    db.session.commit()

    flash("Document removed from this client", "success")
    return redirect(url_for('client_detail', client_id=client_id))


#client documents pending
@app.route('/client/<int:client_id>/pending')
def client_pending(client_id):
    client = Client.query.get_or_404(client_id)
    pending = [cd for cd in client.documents if not cd.received]
    return render_template('pending.html', client=client, pending=pending)




@app.before_first_request
def setup_db():
    db.create_all()
    # Seed master documents
    for t in DEFAULT_TYPES:
        for doc_name in DEFAULT_DOCS.get(t, []):
            exists = Document.query.filter_by(client_type=t, name=doc_name).first()
            if not exists:
                d = Document(client_type=t, name=doc_name)
                db.session.add(d)
    db.session.commit()

if __name__=="__main__":
    app.run(debug=True)
