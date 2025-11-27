"""
Quiz Solver - All quiz solving logic in one file
Combines LLM, data processing, visualization, and quiz orchestration
"""
import re
import json
import io
import base64
import requests
import pandas as pd
import pdfplumber
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import google.generativeai as genai
from browser_module import QuizBrowser
from config import YOUR_EMAIL, YOUR_SECRET, GOOGLE_API_KEY

# ===== LLM Setup =====
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('models/gemini-2.5-pro')


# ===== LLM Functions =====

def analyze_quiz(quiz_text):
    """Ask LLM to understand what the quiz wants"""
    prompt = f"""Look at this quiz and tell me what to do.
    
Quiz: {quiz_text}

Reply in JSON format with:
- task_type: what kind of task (data_analysis, calculation, etc)
- instructions: what needs to be done
- data_sources: any URLs to download
- answer_type: number, string, or json

JSON only:"""

    response = model.generate_content(prompt)
    text = response.text.strip()
    
    # Try to get JSON from response
    try:
        # Remove markdown code blocks if present
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        
        result = json.loads(text)
        return result
    except:
        # Simple fallback
        return {
            "task_type": "calculation",
            "instructions": quiz_text,
            "data_sources": [],
            "answer_type": "string"
        }

def generate_answer(task_info, data):
    """Ask LLM to give the final answer"""
    prompt = f"""Based on this information, give me the answer.

Task: {task_info.get('instructions', '')}
Data: {str(data)[:1000]}

Give ONLY the answer, nothing else."""

    response = model.generate_content(prompt)
    answer = response.text.strip()
    
    # Clean up answer
    answer_type = task_info.get('answer_type', 'string')
    
    if answer_type == 'number':
        # Extract number from text
        nums = re.findall(r'-?\d+\.?\d*', answer)
        if nums:
            return float(nums[0]) if '.' in nums[0] else int(nums[0])
        return 0
    
    return answer


# ===== Data Processing Functions =====

def download_file(url):
    """Download file from URL"""
    print(f"Downloading: {url}")
    response = requests.get(url, timeout=30)
    return response.content

def parse_pdf(file_bytes):
    """Get text and tables from PDF"""
    result = {"text": "", "tables": []}
    
    pdf = pdfplumber.open(io.BytesIO(file_bytes))
    
    # Get all text
    all_text = []
    for i, page in enumerate(pdf.pages):
        page_text = page.extract_text()
        if page_text:
            all_text.append(f"Page {i+1}:\n{page_text}")
        
        # Get tables from this page
        tables = page.extract_tables()
        for table in tables:
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                result["tables"].append(df)
    
    result["text"] = "\n\n".join(all_text)
    pdf.close()
    
    return result

def parse_csv(file_bytes):
    """Parse CSV file"""
    df = pd.read_csv(io.BytesIO(file_bytes))
    return df

def parse_excel(file_bytes):
    """Parse Excel file"""
    df = pd.read_excel(io.BytesIO(file_bytes))
    return df

def analyze_data(df, instruction):
    """Do basic analysis on dataframe"""
    instruction_lower = instruction.lower()
    
    # Find which column to use
    column = None
    for col in df.columns:
        if col.lower() in instruction_lower:
            column = col
            break
    
    if not column and len(df.columns) > 0:
        column = df.columns[1] if len(df.columns) > 1 else df.columns[0]
    
    # Do the operation
    if 'sum' in instruction_lower:
        return df[column].sum()
    elif 'average' in instruction_lower or 'mean' in instruction_lower:
        return df[column].mean()
    elif 'count' in instruction_lower:
        return len(df)
    elif 'max' in instruction_lower:
        return df[column].max()
    elif 'min' in instruction_lower:
        return df[column].min()
    else:
        return df[column].sum()  # default


# ===== Visualization Functions =====

def create_chart(df, title="Chart"):
    """Make a simple bar chart"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Use first two columns
    if len(df.columns) >= 2:
        x_col = df.columns[0]
        y_col = df.columns[1]
        df.plot(kind='bar', x=x_col, y=y_col, ax=ax)
    else:
        df.plot(kind='bar', ax=ax)
    
    ax.set_title(title)
    plt.tight_layout()
    
    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    
    return buf.read()

def to_base64(image_bytes):
    """Convert image to base64 string"""
    b64 = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:image/png;base64,{b64}"


# ===== Main Quiz Solving Logic =====

async def solve_quiz(quiz_url):
    """Solve one quiz"""
    print(f"\n=== Solving quiz: {quiz_url} ===\n")
    
    # Step 1: Get the quiz page
    browser = QuizBrowser(headless=True)
    await browser.start()
    
    page_data = await browser.visit_quiz_page(quiz_url)
    quiz_text = page_data.get('quiz_text', '')
    submit_url = page_data.get('submit_url', '')
    
    await browser.stop()
    
    print(f"Quiz text: {quiz_text[:200]}...")
    
    # Step 2: Ask LLM what to do
    task_info = analyze_quiz(quiz_text)
    print(f"Task type: {task_info.get('task_type')}")
    
    # Step 3: Do the task
    answer = None
    data_sources = task_info.get('data_sources', [])
    
    # Filter out submit URLs from data sources
    actual_files = [url for url in data_sources if '/submit' not in url and any(url.endswith(ext) for ext in ['.pdf', '.csv', '.xlsx', '.xls', '.json'])]
    
    if actual_files:
        # Download the file
        url = actual_files[0]
        file_data = download_file(url)
        
        # Figure out what type of file
        if url.endswith('.pdf'):
            parsed = parse_pdf(file_data)
            if parsed['tables']:
                df = parsed['tables'][0]
                answer = analyze_data(df, task_info.get('instructions', ''))
            else:
                answer = generate_answer(task_info, parsed['text'])
        
        elif url.endswith('.csv'):
            df = parse_csv(file_data)
            answer = analyze_data(df, task_info.get('instructions', ''))
        
        elif url.endswith(('.xlsx', '.xls')):
            df = parse_excel(file_data)
            answer = analyze_data(df, task_info.get('instructions', ''))
        
        # Check if we need to make a chart
        if 'chart' in quiz_text.lower() or 'visualiz' in quiz_text.lower():
            img = create_chart(df, "Chart")
            answer = to_base64(img)
    else:
        # No files, just ask LLM
        answer = generate_answer(task_info, quiz_text)
    
    print(f"Answer: {answer}")
    
    # Step 4: Submit answer
    if not submit_url:
        # Try to find submit URL in text
        urls = re.findall(r'https?://[^\s<>"]+/submit[^\s<>"]*', quiz_text)
        if urls:
            submit_url = urls[0]
    
    if submit_url:
        payload = {
            "email": YOUR_EMAIL,
            "secret": YOUR_SECRET,
            "url": quiz_url,
            "answer": answer
        }
        
        print(f"Submitting to: {submit_url}")
        response = requests.post(submit_url, json=payload, timeout=30)
        result = response.json()
        
        print(f"Result: {result}")
        
        return {
            "success": result.get('correct', False),
            "next_url": result.get('url'),
            "answer": answer
        }
    
    return {"success": False, "error": "No submit URL found"}

async def solve_quiz_chain(start_url):
    """Solve multiple quizzes in a chain"""
    current_url = start_url
    results = []
    count = 0
    
    while current_url and count < 5:  # max 5 quizzes
        count += 1
        result = await solve_quiz(current_url)
        results.append(result)
        
        if result.get('success') and result.get('next_url'):
            current_url = result['next_url']
        else:
            break
    
    return {
        "success": True,
        "quizzes_solved": count,
        "results": results
    }
