from groq import Groq
import json
import re
import os

def review_pull_request(diff_content):
    """
    Review a pull request by analyzing the diff content using Groq API.
    
    Args:
        diff_content (str): The git diff content to analyze
        
    Returns:
        str: JSON response from the API containing review details
    """
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=GROQ_API_KEY)
    
    messages = [
       {
            "role": "system",
            "content": '''You are a github pull request reviewer and you are used in an application
             your task is to analyze the code of pull request and tell give the json response with details:
             output: { 
              "review": "this is a todo list update code with chang ein list design", #this gives the complete review of the pull request 
              "review_score": 80, #this is the total correct percentage score of code like 80% in this case
              "errors":
              [{
                "type": "TODO",#here you tell what this code is about
                "severity": "warning", #here you tell the severity of the issue in the code
                "message": "TODO comment found in code", #reasons for this severity like variable missing syntax error etc
                "line": 10, #number of the line where the issue exists
                "file-name":"todo.py" #name of the file for which this issue is found
                "suggestion": "suggestions to remove these issues"
            }]
            }

            make sure only give me json reponse not anything else
            try to write things concise but deliver the proper message and easy to understandable
            this code is comparing both codes with differnt file don't consider the changings in two file as a error just check that the new code that is going to push is correct , ignore new lines extra spaces if this don't effect indentation
            
            -STEPS:
             1. take the both codes and first seperate them as differnt code files
             2. then check weather the code of each file is correct or contain errors
             3. if there is error add this error in list of errors for this file 
             4. if there is no error check weather the new code belong to same file if yes then check if we merge both code is this cause any errors if yes add to array
            
            Purpose: the purpose of doing this is to get review on new upcomming code in a pull request and tell the user either the code is correct or cause any error
            '''
        },
        {
            "role": "user",
            "content": diff_content
        }
    ]

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        raw = completion.choices[0].message.content
        json_str = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        data = json.loads(json_str)
        print(data)
        return data
    except Exception as e:
        return f"Error: {str(e)}"

# Example usage
if __name__ == "__main__":
    # Example diff content
    sample_diff = '''
    diff --git a/abdullah.py b/abdullah.py
new file mode 100644
index 0000000..f905382
--- /dev/null
+++ b/abdullah.py
@@ -0,0 +1,5 @@
+a = 0
+b = 9
+sum_Num = a + b
+
+print(sum_Num)
\ No newline at end of file
diff --git a/check.py b/check.py
index 5ccd02b..7b2e9cc 100644
--- a/check.py
+++ b/check.py
@@ -1 +1,2 @@
 #hi how are you
+
    '''
    
    result = review_pull_request(sample_diff)
    print(result)