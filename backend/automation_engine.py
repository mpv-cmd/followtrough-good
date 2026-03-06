def run_full_analysis(transcript, actions, meetings):

    results = {}

    from summarize_meeting import summarize_meeting
    from meeting_score_ai import generate_meeting_score
    from insight_engine import generate_insights
    from predictive_engine import predict_project_risks
    from followup_email_ai import generate_followup_email

    summary = summarize_meeting(transcript)

    score = generate_meeting_score(transcript)

    insights = generate_insights(meetings, actions)

    predictions = predict_project_risks(meetings, actions)

    email = generate_followup_email(summary, actions, "")

    results["summary"] = summary
    results["meeting_score"] = score
    results["insights"] = insights
    results["predictions"] = predictions
    results["followup_email"] = email

    return results