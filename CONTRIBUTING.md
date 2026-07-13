# Contributing to TenderTracker

Thank you for helping make TenderTracker better! This document details how to report issues, suggest improvements, and contribute code.

## 🐛 Reporting Issues

If you find a bug, please check the existing issues on GitHub first. If it's a new issue, please open a new issue using our **Bug Report Template** and provide as much context as possible:

1. **Describe the Bug**: A clear description of what went wrong.
2. **Steps to Reproduce**: Detailed steps so we can reproduce it locally.
3. **Expected Behavior**: What should have happened.
4. **Environment Info**:
   - Operating System (Windows, macOS, Linux)
   - Python Version (`python --version`)
   - LLM Provider / Model (LM Studio, Ollama, Gemini)
5. **Logs & Screen Captures**: Attach terminal log outputs or screenshots if relevant.

---

## 💡 Recommending Improvements & Feature Requests

We love ideas to make TenderTracker better! To request a feature or suggest an optimization, please use our **Feature Request Template**:

* **Goal**: What problem are you trying to solve?
* **Description**: A clear and detailed description of the proposed feature.
* **Alternatives Considered**: Any other approaches you've considered.
* **Benefits**: Why would this be useful to users?

---

## 🛠️ Development Workflow

To contribute code:

1. **Clone the Repo**:
   ```bash
   git clone https://github.com/Jaiswal-ruhil/tenderTracker.git
   cd tenderTracker
   ```
2. **Setup Virtual Environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # macOS/Linux
   pip install -r requirements.txt
   ```
3. **Run Dev Mode**:
   ```bash
   python run_dev.py
   ```
4. **Running Unit Tests**:
   Before submitting changes, make sure all tests pass:
   ```bash
   .venv\Scripts\python.exe -m unittest discover tests
   ```
5. **Submit a Pull Request**: Push to your branch and create a PR describing your changes.
