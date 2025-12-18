from flask import Flask, render_template, request, jsonify
from weather.met import fetch_met
from logic.spray import judge
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    try:
        lat = float(request.args.get('lat', 35.5))
        lon = float(request.args.get('lon', 139.6))
        
        app.logger.info(f"Fetching forecast for lat={lat}, lon={lon}")
        data = fetch_met(lat, lon)
        ts = data["properties"]["timeseries"]
        results = judge(ts)
        
        return jsonify({
            'success': True,
            'results': results,
            'location': {'lat': lat, 'lon': lon}
        })
    except Exception as e:
        app.logger.error(f"Error fetching forecast: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)