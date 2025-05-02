# 🧠 Text-to-SQL Code Generation and Execution

This project, developed as part of the HPE Internship Program, enables users to convert natural language queries into SQL statements using a fine-tuned T5 model. It provides an end-to-end solution to generate and execute SQL queries on a PostgreSQL database through a user-friendly interface built with Streamlit and FastAPI.

---

## 🚀 Features

- Generate SQL queries from plain English.
- Execute SQL statements against a live PostgreSQL database.
- User interface built with **Streamlit**.
- Backend API powered by **FastAPI**.
- Uses a fine-tuned **T5 model** for SQL generation.

---

## 📁 Project Structure

2. Create and Activate a Virtual Environment
python -m venv myvenv
myvenv\Scripts\activate  # For Windows

3. Check Python & Pip Versions
python --version (3.8.0 - < 3.12.0)
pip --version 

4. Upgrade Pip
python -m pip install --upgrade pip

5.Install Dependencies 
pip install -r requirements.txt

🧪 Running the Application
1. Start the FastAPI Backend  run:

 uvicorn main:app --reload --port 8000

3. Launch the Streamlit Frontend
Open a new terminal and activate the virtual environment again, then run:
streamlit run app.py

🗄️ Database Configuration
Ensure that your PostgreSQL instance is running and accessible. Update your database credentials inside the appropriate configuration file or environment variables.

🤖 Model
This project uses a fine-tuned version of the T5 model on the WikiSQL dataset to translate natural language questions into valid SQL queries.

📌 License
This project is licensed under the MIT License.

✍️ Acknowledgments
Special thanks to the HPE Internship Program and mentors for their continuous support and guidance throughout the development of this project.





