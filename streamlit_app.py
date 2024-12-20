import streamlit as st
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
import re
import os
import tempfile
from gtts import gTTS
from typing import Optional, Dict, Any
from pydub import AudioSegment
from pydub.effects import low_pass_filter, high_pass_filter

# Page configuration
st.set_page_config(page_title="Transcript Genie - Smart Document Summarizer", page_icon="📝", layout="wide")

# Custom CSS styling
st.markdown("""
    <style>
    .stApp {
        background-color: #311445;
        color: #ffffff;
    }
    
    # .stMarkdown, .stText, .element-container {
        # background-color: rgba(255, 255, 255, 0.05);
        # padding: 1rem;
        # border-radius: 10px;
        # margin: 0.5rem 0;
    # }
    
    .stButton > button {
        background-color: #6b2c91;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        width: 100%;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background-color: #8a37b8;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    .stDownloadButton > button {
        background-color: #4a1d6b;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        width: 100%;
        margin: 0.5rem 0;
        transition: all 0.3s ease;
    }
    
    .stRadio > label {
        color: white !important;
    }
    
    .stTextInput > div > div > input {
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 5px;
    }
    
    .stAlert {
        background-color: rgba(107, 44, 145, 0.2);
        color: white;
        border: 1px solid rgba(107, 44, 145, 0.3);
        border-radius: 5px;
    }

    .stTextArea > div > div > textarea {
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 5px;
    }

    .stSelectbox > div > div > div {
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

def extract_video_id(youtube_url):
    """Extract video ID from YouTube URL."""
    video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', youtube_url)
    return video_id_match.group(1) if video_id_match else None

def get_youtube_transcript(video_id):
    """Get transcript from YouTube video."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = ' '.join([item['text'] for item in transcript_list])
        return transcript_text
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"

def generate_summary(text, summary_type, api_key):
    """Generate summary using Gemini."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    
    prompts = {
        'detailed': """Create a comprehensive summary that captures all main topics and key points, preserving important details and context.""",
        'brief': """Create a concise 2-3 paragraph summary that captures the core message and highlights the most important points.""",
        'bullet': """Create a bullet-point summary that lists the key takeaways in order of importance."""
    }
    
    try:
        response = model.generate_content(f"{prompts[summary_type]}\n\n{text}")
        return response.text
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def generate_conversational_summary(text, api_key):
    """Generate conversational summary using Gemini."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    
    conversational_prompt = """
    Create an engaging conversational summary of the following text as a natural dialogue between Alice and Bob.
    Requirements:
    1. Format each line as 'Speaker: Dialogue' (MUST start every line with either 'Alice:' or 'Bob:')
    2. Make it feel like a real conversation, not just Q&A
    3. Both speakers should contribute insights and knowledge
    4. Include reactions and follow-up questions
    5. Keep the technical accuracy of the original content
    6. Use natural language and conversational tone
    7. Maintain equal participation from both speakers
    8. Add natural transitions between topics
    9. Keep each speaker's style consistent

    Here's the text to summarize in a conversation:
    {text}

    Remember: Every single line MUST start with either 'Alice:' or 'Bob:' for proper audio processing.
    """
    
    try:
        response = model.generate_content(conversational_prompt.format(text=text))
        conversation_lines = response.text.split('\n')
        formatted_lines = []
        
        for line in conversation_lines:
            line = line.strip()
            if line:
                if not (line.startswith('Alice:') or line.startswith('Bob:')):
                    continue
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    except Exception as e:
        return f"Error generating conversational summary: {str(e)}"

def process_line_for_audio(line_text: str, speaker: str, temp_files: list) -> AudioSegment:
    """Process a single line of dialogue into audio with speaker-specific modifications."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
    temp_files.append(temp_file.name)
    
    tts = gTTS(text=line_text, lang="en", slow=False)
    tts.save(temp_file.name)
    
    audio_segment = AudioSegment.from_mp3(temp_file.name)
    
    if speaker.lower() == "bob":
        # Make Bob's voice deeper and slightly slower
        modified_audio = audio_segment._spawn(audio_segment.raw_data, overrides={
            "frame_rate": int(audio_segment.frame_rate * 0.85)  # Slower speed for deeper voice
        })
        modified_audio = modified_audio.set_frame_rate(audio_segment.frame_rate)
        # Add some bass boost for Bob
        modified_audio = modified_audio.low_pass_filter(3000)
    else:  # Alice
        # Make Alice's voice slightly higher and clearer
        modified_audio = audio_segment._spawn(audio_segment.raw_data, overrides={
            "frame_rate": int(audio_segment.frame_rate * 1.15)  # Faster speed for higher pitch
        })
        modified_audio = modified_audio.set_frame_rate(audio_segment.frame_rate)
        # Add some treble boost for Alice
        modified_audio = modified_audio.high_pass_filter(1000)
    
    return modified_audio

def generate_audio_summary(summary: str) -> str:
    """Generate conversational audio with two distinct voices."""
    combined_audio = AudioSegment.empty()
    temp_files = []
    
    try:
        # Add intro sound
        intro_silence = AudioSegment.silent(duration=1000)  # 1 second intro silence
        combined_audio += intro_silence
        
        lines = summary.split('\n')
        prev_speaker = None
        
        for line in lines:
            parts = line.split(':', 1)
            if len(parts) < 2:
                continue
                
            speaker = parts[0].strip()
            line_text = parts[1].strip()
            
            if not line_text:
                continue
            
            # Add longer pause between different speakers
            if prev_speaker and prev_speaker != speaker:
                combined_audio += AudioSegment.silent(duration=800)  # 0.8s pause between speakers
            else:
                combined_audio += AudioSegment.silent(duration=400)  # 0.4s pause same speaker
                
            # Process the line with speaker-specific modifications
            audio_segment = process_line_for_audio(line_text, speaker, temp_files)
            
            # Fade in/out for smoother transitions
            audio_segment = audio_segment.fade_in(50).fade_out(50)
            
            combined_audio += audio_segment
            prev_speaker = speaker
        
        # Add outro sound
        outro_silence = AudioSegment.silent(duration=1000)  # 1 second outro silence
        combined_audio += outro_silence
        
        # Export final audio
        final_output = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        combined_audio.export(final_output.name, format="mp3", 
                            parameters=["-q:a", "0"])  # Highest quality MP3
        
        # Cleanup temp files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except Exception:
                pass
                
        return final_output.name
        
    except Exception as e:
        # Cleanup on error
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except Exception:
                pass
        raise Exception(f"Error generating audio summary: {str(e)}")

def main():
    st.title("📝 Transcript Genie")
    st.subheader("YouTube Transcript Generator & AI Summarizer")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        api_key = st.text_input("🔑 Enter your Gemini API Key:", type="password", help="Your API key will be used securely and not stored")
        input_method = st.radio("Select input method:", ["YouTube URL", "Upload Transcript", "Paste Transcript"])
    
    with col2:
        st.info("💡 **Pro Tips:**\n"
                "- Use YouTube URL for direct transcript\n"
                "- Upload txt files for offline use\n"
                "- Paste text for quick processing")
    
    text_to_summarize = None
    
    if input_method == "YouTube URL":
        youtube_url = st.text_input("🔗 Enter YouTube URL:")
        if youtube_url:
            video_id = extract_video_id(youtube_url)
            if video_id:
                transcript = get_youtube_transcript(video_id)
                if not transcript.startswith("Error"):
                    text_to_summarize = transcript
                    st.success("Transcript fetched successfully!")
                else:
                    st.error(transcript)
    
    elif input_method == "Upload Transcript":
        uploaded_file = st.file_uploader("📤 Upload transcript file", type=['txt'])
        if uploaded_file:
            text_to_summarize = uploaded_file.getvalue().decode()
            st.success("File uploaded successfully!")
    
    elif input_method == "Paste Transcript":
        text_to_summarize = st.text_area("📝 Paste transcript here:", height=200)
    
    if text_to_summarize and api_key:
        col1, col2 = st.columns(2)
        
        with col1:
            summary_type = st.selectbox("Choose summary style:", ["detailed", "brief", "bullet"])
            if st.button("🚀 Generate Summary", use_container_width=True):
                with st.spinner("Generating summary..."):
                    summary = generate_summary(text_to_summarize, summary_type, api_key)
                    st.markdown("### Generated Summary")
                    st.write(summary)
                    st.download_button(
                        "📥 Download Summary",
                        summary,
                        f"{summary_type}_summary.txt",
                        use_container_width=True
                    )
        
        with col2:
            if st.button("🎧 Generate Conversation", use_container_width=True):
                with st.spinner("Generating conversation..."):
                    conversation = generate_conversational_summary(text_to_summarize, api_key)
                    st.markdown("### Conversational Summary")
                    
                    # Format the conversation with custom styling
                    styled_conversation = ""
                    for line in conversation.split('\n'):
                        if line.strip():
                            # Split into speaker and text
                            parts = line.split(':', 1)
                            if len(parts) == 2:
                                speaker, text = parts
                                # Add custom styling for each line
                                styled_conversation += f"""
                                <div style='
                                    background-color: rgba(255, 255, 255, 0.05);
                                    padding: 10px;
                                    margin: 5px 0;
                                    border-radius: 5px;
                                    border-left: 3px solid {("#8a37b8" if "Alice" in speaker else "#4a1d6b")};
                                '>
                                    <span style='
                                        color: #b794f4;
                                        font-weight: bold;
                                    '>{speaker}:</span>
                                    <span style='color: #ffffff;'>{text}</span>
                                </div>
                                """
                    
                    # Display the styled conversation
                    st.markdown(styled_conversation, unsafe_allow_html=True)
                    
                    with st.spinner("Creating audio..."):
                        try:
                            audio_file = generate_audio_summary(conversation)
                            st.audio(audio_file)
                            col1, col2 = st.columns(2)
                            with col1:
                                st.download_button(
                                    "📥 Download Audio",
                                    open(audio_file, 'rb'),
                                    "conversation.mp3",
                                    use_container_width=True
                                )
                            with col2:
                                st.download_button(
                                    "📥 Download Text",
                                    conversation,
                                    "conversation.txt",
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: rgba(255,255,255,0.7);'>
      <p>"### Transcript Generator and Summarizer - From lengthy YouTube vedios to concise insights") </p>
      <p>"📝 YouTube Transcripts | 📄 Upload Documents | 📊 Get Summaries | 🎯 Extract Insights") </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
