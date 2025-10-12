# create_sample_quiz.py
from fiturBot.quiz_handler import quiz_manager
from datetime import datetime

def create_sample_quizzes():
    """Create sample quizzes for testing"""
    
    # Sample quiz 1: Basic Russian
    quiz1_questions = [
        {
            'question': 'Apa bahasa Rusia untuk "Halo"?',
            'options': ['Привет', 'Спасибо', 'Пока', 'До свидания'],
            'correct_answer': 0
        },
        {
            'question': 'Apa arti "Спасибо"?',
            'options': ['Selamat tinggal', 'Terima kasih', 'Tolong', 'Permisi'],
            'correct_answer': 1
        },
        {
            'question': 'Bagaimana mengucapkan "Nama saya" dalam bahasa Rusia?',
            'options': ['Меня зовут', 'Как дела', 'Доброе утро', 'Сколько стоит'],
            'correct_answer': 0
        }
    ]
    
    quiz_manager.create_quiz(
        "sample_russian_basics",
        "Dasar-dasar Bahasa Rusia",
        quiz1_questions,
        "system"
    )
    
    # Sample quiz 2: Russian Culture
    quiz2_questions = [
        {
            'question': 'Apa ibu kota Rusia?',
            'options': ['Saint Petersburg', 'Moscow', 'Kazan', 'Novosibirsk'],
            'correct_answer': 1
        },
        {
            'question': 'Mata uang resmi Rusia adalah?',
            'options': ['Euro', 'Dollar', 'Rubel', 'Yen'],
            'correct_answer': 2
        },
        {
            'question': 'Monumen terkenal di Moskow berupa katedral berwarna-warni disebut?',
            'options': ['Kremlin', 'St. Basil Cathedral', 'Bolshoi Theatre', 'Hermitage'],
            'correct_answer': 1
        }
    ]
    
    quiz_manager.create_quiz(
        "sample_russian_culture", 
        "Budaya dan Geografi Rusia",
        quiz2_questions,
        "system"
    )
    
    print("✅ Sample quizzes created!")

if __name__ == "__main__":
    create_sample_quizzes()
