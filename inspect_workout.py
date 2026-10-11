from app import app
client = app.test_client()
with client.session_transaction() as sess:
    sess['user_id'] = 'test_user_123'
r = client.get('/workout')
print('STATUS:', r.status_code)
h = r.get_data(as_text=True)
print('exerciseGrid:', 'exerciseGrid' in h)
print('renderExercises:', 'renderExercises' in h)
print('loadExercises:', 'loadExercises' in h)
print('shell.js:', 'shell.js' in h)
print('startBtn:', 'startBtn' in h)
print('welcomeCard:', 'welcomeCard' in h)
print('sessionArea:', 'sessionArea' in h)
print('LEN:', len(h))
print('LEN:', len(h))
# Check what scripts are loaded
import re
scripts = re.findall(r'src=["\']([^"\']+)["\']', h)
print('Scripts:', scripts)
# Check for the init call
print('init() called:', 'init()' in h)
# Check for exercises.html vs workout.html content
print('Choose an exercise:', 'Choose an exercise' in h)
print('START SESSION:', 'START SESSION' in h)
# Check the API call
print('api/exercises call:', '/api/exercises' in h)
print('window.api.get:', 'window.api.get' in h)

# Now test the exercises endpoint
r2 = client.get('/api/exercises')
print('\n/api/exercises status:', r2.status_code)
data = r2.get_json()
if data and data.get('data'):
    exercises = data['data']
    print('Exercise count:', len(exercises))
    for ex in exercises:
        print(f'  id={ex["id"]}, name={ex["name"]}, muscles={ex.get("muscles", [])}')
