from src.performance_analyzer import analyze_performance
if __name__ == "__main__":
    report = analyze_performance()
    print(f"Analysis completed: {report.get('summary')}")
