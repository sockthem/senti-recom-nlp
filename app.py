
from flask import Flask, render_template, request

import model

app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')

@app.route("/recommend", methods=['POST'])
def recommend():
    if (request.method == 'POST'):
        username = request.form['User_Name']
        rc = model.rcmd(username)
        
        return render_template('index.html', column_names=rc.columns.values, row_data=list(rc.values.tolist()), zip=zip)
    else:
        return render_template('index.html')



if __name__ == '__main__':
    app.debug=True
    app.run()
