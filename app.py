from flask import Flask, Response
from flask import request
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import base64

app = Flask(__name__)

def populate_screenshot(misclassification):
    try:
        resp = requests.get('http://screenshoter:8080/take', timeout=20, params={
            'url': misclassification['url'],
            'format': 'jpeg',
            'quality': 60,
            'timeout': 15000
        })

        if not resp.status_code == 200:
            return None
        
        misclassification['screenshot'] = {
            "base64": base64.b64encode(resp.content).decode(),
            "ext": "jpg"
        }
    except Exception:
        return None

    return misclassification
    

@app.route("/api/<api_version>/submission/<uuid>/report_issue", methods=["POST"])
def proxy_report(api_version, uuid):
    body = request.json
    if body.get('url_misclassifications'):
        try:
            with ThreadPoolExecutor(16) as executor:
                result_futures = list(map(lambda x: executor.submit(populate_screenshot, x), body.get('url_misclassifications')))
                url_misclassifications = [f.result() for f in as_completed(result_futures)]
            
            url_misclassifications = [misclass for misclass in url_misclassifications if misclass is not None]
            body['url_misclassifications'] = url_misclassifications

            if not url_misclassifications:
                return {"message": "Couldn't screenshot pages, nothing was reported", "total_reported": 0}, 200

            resp = requests.post(f'https://report.netcraft.com/api/{api_version}/submission/{uuid}/report_issue', json=body)

            if resp.status_code != 200:
                try:
                    resp_json = resp.json()
                    return resp_json, resp.status_code
                except Exception:
                    return resp.text, resp.status_code
            
            resp_json = resp.json()
            resp_json['total_reported'] = len(url_misclassifications)

            return resp_json, 200
        except Exception as ex:
            return {"error": str(ex)}, 500

