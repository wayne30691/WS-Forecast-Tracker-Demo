# WS-Forecast-Tracker-GitHub-Demo

A Streamlit demo version of the original **WS-Forecast-Tracker** that can read its CSV data files directly from **GitHub raw URLs**.

## What changed

This version is intended for demo use.

- Default data source mode is **GitHub demo**
- The app reads these files directly from your repo:
  - `Data Source/Set_Up_All_RF_data.csv`
  - `Data Source/Allocation_data.csv`
  - `Data Source/Set_Up_PI_data.csv`
- You can still switch back to **Upload CSV files** in the sidebar
- GitHub owner / repo / branch / folder are configurable in the sidebar, so the same app can be reused across branches or renamed repositories

## Recommended new repo name

`WS-Forecast-Tracker-GitHub-Demo`

Other good options:
- `WS-Forecast-Tracker-Demo`
- `WS-Forecast-Tracker-Streamlit-Demo`
- `Forecast-Publish-Comparison-Demo`

## How it works

In **GitHub demo** mode, the app builds raw GitHub URLs in this pattern:

```text
https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<folder>/<file_name>
```

Example:

```text
https://raw.githubusercontent.com/wayne30691/WS-Forecast-Tracker/main/Data%20Source/Allocation_data.csv
```

## How to run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## For Streamlit Cloud deployment

After you rename the repository, update the default repo value in `streamlit_app.py` if you want the app to point to the new repository automatically:

```python
github_repo = st.text_input("GitHub repo", value="WS-Forecast-Tracker-GitHub-Demo")
```

## Important note for demo readiness

The app requires a **non-empty** `Set_Up_All_RF_data.csv` file in the GitHub data folder.
If that file is empty, the app will stop and ask for a valid file.

## Files

- `streamlit_app.py` — GitHub-data-source-ready app
- `requirements.txt` — dependencies
- `README.md` — project documentation
