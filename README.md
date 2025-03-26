Approach & Challenges
#Approach:
1.Designed API routes as per the assignment manual.

2.Selected appropriate modules for efficient implementation.

3.Set up a new MongoDB cluster for data storage.

4.Generated an API key for Mistral LLM to integrate AI-powered responses.

5.Implemented RESTful endpoints to handle POST, GET, and DELETE requests for seamless accessibility.

6.At last used claude ai to add comments and doc strings in the script

#Challenges:
1.Transitioning from Django to FastAPI – Since I primarily use Django, adapting to FastAPI required understanding its async architecture and dependency injection model.

2.Learning MongoDB – Despite being new to NoSQL databases, I found MongoDB intuitive and easy to work with, especially using Motor (an async driver).

This project provided valuable hands-on experience with FastAPI, MongoDB, and external API integration, helping me expand my skill set beyond Django. 


COMMANDS TO RUN:
1.pip install -r requirements.txt
2.uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
