import os
from dotenv import load_dotenv
from src.agent import run_research_crew

def main():
    # 1. Load the GEMINI_API_KEY from the local .env file
    load_dotenv()
    
    # 2. Validate environment
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY not found.")
        print("Please ensure your .env file contains: GEMINI_API_KEY=your_actual_api_key")
        return

    print("🌍 Global Intelligence Agent Initialized 🌍")
    print("Type 'exit' or 'quit' to terminate the session.")
    
    # 3. Interactive Execution Loop
    while True:
        user_query = input("\nAsk a global intelligence or weather question: ")
        
        if user_query.lower() in ['exit', 'quit']:
            print("Shutting down agent session...")
            break
            
        if not user_query.strip():
            continue
            
        print("\nAgent is analyzing and executing tools...\n" + "-"*50)
        
        try:
            # Trigger the CrewAI workflow
            response = run_research_crew(user_query)
            
            # Print the final synthesized markdown output
            print("\n" + "="*50)
            print("FINAL BRIEFING:")
            print("="*50)
            print(response)
            
        except Exception as e:
            print(f"\nAn error occurred during execution: {e}")

if __name__ == "__main__":
    main()