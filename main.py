#!/usr/bin/env python3
"""
Fetches stats, trims videos, downloads them, and adds subtitles
"""

import sys
import os
import re
import json
from datetime import datetime
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp is required. Install with: pip install yt-dlp")
    sys.exit(1)

try:
    import ffmpeg
except ImportError:
    print("Error: ffmpeg-python is required. Install with: pip install ffmpeg-python")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'
    
    @staticmethod
    def colorize(text, color):
        return f"{color}{text}{Colors.END}"


class YouTubeProcessor:
    def __init__(self):
        self.video_info = None
        self.video_url = None
        self.available_subtitles = {}
        self.quality_options = {
            '1': ('best[height<=360]/best', '360p'),
            '2': ('best[height<=480]/best', '480p'), 
            '3': ('best[height<=720]/best', '720p'),
            '4': ('best[height<=1080]/best', '1080p'),
            '5': ('best', 'Best available')
        }
        
    def validate_url(self, url):
        """Validate YouTube URL"""
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
            r'(?:https?://)?(?:m\.)?youtube\.com/watch\?v=[\w-]+'
        ]
        return any(re.match(pattern, url.strip()) for pattern in youtube_patterns)
    
    def fetch_stats(self, url):
        """Fetch video statistics and metadata"""
        if not self.validate_url(url):
            raise ValueError("Invalid YouTube URL format")
        
        self.video_url = url.strip()
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print("Fetching video information...")
                self.video_info = ydl.extract_info(self.video_url, download=False)
                
                # Get available subtitles
                self.available_subtitles = self.video_info.get('subtitles', {})
                auto_subtitles = self.video_info.get('automatic_captions', {})
                
                # Merge manual and auto subtitles
                all_subtitles = {**self.available_subtitles, **auto_subtitles}
                self.available_subtitles = all_subtitles
                
            return {
                'title': self.video_info.get('title', 'N/A'),
                'duration': self._format_duration(self.video_info.get('duration', 0)),
                'duration_seconds': self.video_info.get('duration', 0),
                'view_count': self._format_number(self.video_info.get('view_count', 0)),
                'like_count': self._format_number(self.video_info.get('like_count', 0)),
                'upload_date': self._format_date(self.video_info.get('upload_date', '')),
                'uploader': self.video_info.get('uploader', 'N/A'),
                'description': self.video_info.get('description', 'N/A')[:100] + '...' if self.video_info.get('description') else 'N/A',
                'has_subtitles': len(self.available_subtitles) > 0
            }
        except Exception as e:
            raise Exception(f"Failed to fetch video info: {str(e)}")
    
    def get_subtitle_languages(self):
        """Get available subtitle languages"""
        if not self.available_subtitles:
            return []
        
        # Prefer manual subtitles over auto-generated
        manual_subs = self.video_info.get('subtitles', {})
        auto_subs = self.video_info.get('automatic_captions', {})
        
        languages = []
        
        # Add manual subtitles first
        for lang in manual_subs.keys():
            lang_name = self._get_language_name(lang)
            languages.append((lang, f"{lang_name} (Manual)", 'manual'))
        
        # Add auto-generated subtitles
        for lang in auto_subs.keys():
            if lang not in manual_subs:  # Don't duplicate
                lang_name = self._get_language_name(lang)
                languages.append((lang, f"{lang_name} (Auto)", 'auto'))
        
        return languages
    
    def _get_language_name(self, lang_code):
        """Get language name from code"""
        lang_names = {
            'en': 'English',
            'es': 'Spanish', 
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'hi': 'Hindi'
        }
        return lang_names.get(lang_code, lang_code.upper())
    
    def select_subtitle_language(self):
        """Let user select subtitle language"""
        languages = self.get_subtitle_languages()
        
        if not languages:
            return None
        
        print(f"\nAvailable subtitles:")
        for i, (code, name, type_) in enumerate(languages, 1):
            marker = "[M]" if type_ == 'manual' else "[A]"
            print(f"  {i}. {marker} {name}")
        
        while True:
            try:
                choice = input(f"Select subtitle (1-{len(languages)}): ").strip()
                if not choice:
                    return None
                
                idx = int(choice) - 1
                if 0 <= idx < len(languages):
                    selected = languages[idx]
                    print(f"Selected: {selected[1]}")
                    return selected[0]  # Return language code
                else:
                    print("Invalid choice. Try again.")
            except ValueError:
                print("Please enter a number.")
            except KeyboardInterrupt:
                return None
    
    def _format_duration(self, seconds):
        """Convert seconds to HH:MM:SS format"""
        if not seconds:
            return "N/A"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def _format_number(self, num):
        """Format large numbers with commas"""
        if not num:
            return "0"
        return f"{num:,}"
    
    def _format_date(self, date_str):
        """Format upload date"""
        if not date_str:
            return "N/A"
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            return date_obj.strftime('%Y-%m-%d')
        except:
            return date_str
    
    def parse_timestamp(self, timestamp):
        """Parse timestamp in format HH:MM:SS or MM:SS to seconds"""
        try:
            timestamp = timestamp.strip()
            parts = timestamp.split(':')
            
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            else:
                raise ValueError("Invalid format")
        except (ValueError, TypeError):
            raise ValueError("Timestamp must be in MM:SS or HH:MM:SS format (e.g., 1:30 or 1:30:45)")
    
    def validate_timestamps(self, start_time, end_time):
        """Validate start and end timestamps"""
        start_seconds = self.parse_timestamp(start_time)
        end_seconds = self.parse_timestamp(end_time)
        
        if start_seconds >= end_seconds:
            raise ValueError("Start time must be before end time")
        
        video_duration = self.video_info.get('duration', 0)
        if start_seconds >= video_duration:
            raise ValueError(f"Start time exceeds video duration ({self._format_duration(video_duration)})")
        
        if end_seconds > video_duration:
            raise ValueError(f"End time exceeds video duration ({self._format_duration(video_duration)})")
        
        return start_seconds, end_seconds
    
    def get_quality_choice(self):
        """Get user's quality preference"""
        print(f"\nVideo quality options:")
        print(f"  1. 360p")
        print(f"  2. 480p") 
        print(f"  3. 720p (Recommended)")
        print(f"  4. 1080p")
        print(f"  5. Best available")
        
        while True:
            choice = input("Select quality (1-5): ").strip()
            if choice in self.quality_options:
                format_str, quality_name = self.quality_options[choice]
                print(f"Selected: {quality_name}")
                return format_str
            print("Invalid choice. Please enter 1-5.")
    
    def download_and_trim(self, start_time, end_time, quality_format, subtitle_lang=None, output_path=None):
        """Download video and trim to specified time range with optional subtitles"""
        if not self.video_info:
            raise ValueError("No video info available. Fetch stats first.")
        
        # Validate timestamps
        start_seconds, end_seconds = self.validate_timestamps(start_time, end_time)
        
        # Generate output filename if not provided
        if not output_path:
            safe_title = "".join(c for c in self.video_info['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:50]  # Limit filename length
            output_path = f"{safe_title}_{start_time.replace(':', '-')}_to_{end_time.replace(':', '-')}.mp4"
        
        # Download video
        temp_video = "temp_video.%(ext)s"
        
        ydl_opts = {
            'format': quality_format,
            'outtmpl': temp_video,
            'quiet': True,
        }
        
        # Add subtitle options if requested
        if subtitle_lang:
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': [subtitle_lang],
                'subtitlesformat': 'srt',  # Changed to SRT format for better compatibility
            })
        
        print("Downloading video...")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.video_url])
            
            # Find the actual downloaded files
            video_files = [f for f in os.listdir('.') if f.startswith('temp_video') and not f.endswith(('.srt', '.vtt'))]
            if not video_files:
                raise Exception("Downloaded video file not found")
            
            actual_video_file = video_files[0]
            
            # Check for subtitle file
            subtitle_files = [f for f in os.listdir('.') if f.startswith('temp_video') and f.endswith('.srt')]
            actual_subtitle_file = subtitle_files[0] if subtitle_files else None
            
            # Trim video using ffmpeg
            print(f"Trimming video from {start_time} to {end_time}...")
            duration = end_seconds - start_seconds
            
            # Build ffmpeg command
            input_video = ffmpeg.input(actual_video_file, ss=start_seconds, t=duration)
            
            if actual_subtitle_file and subtitle_lang:
                print("Adding subtitles...")
                # Create a temporary trimmed subtitle file
                temp_trimmed_subs = "temp_trimmed_subs.srt"
                self._trim_subtitle_file(actual_subtitle_file, temp_trimmed_subs, start_seconds, end_seconds)
                
                # Burn subtitles into video
                output = ffmpeg.output(
                    input_video,
                    output_path,
                    vf=f"subtitles={temp_trimmed_subs}:force_style='FontSize=20,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2,Shadow=1'"
                )
            else:
                output = ffmpeg.output(input_video, output_path, c='copy')
            
            # Run ffmpeg with error handling
            try:
                output.overwrite_output().run(capture_stdout=True, capture_stderr=True)
            except ffmpeg.Error as e:
                # If subtitle burning fails, try without subtitles
                if actual_subtitle_file:
                    print("Subtitle processing failed, saving video without subtitles...")
                    output = ffmpeg.output(input_video, output_path, c='copy')
                    output.overwrite_output().run(capture_stdout=True, capture_stderr=True)
                else:
                    raise e
            
            # Clean up temp files
            temp_files = [f for f in os.listdir('.') if f.startswith('temp_video') or f.startswith('temp_trimmed_subs')]
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            return output_path
            
        except Exception as e:
            # Clean up temp files if they exist
            temp_files = [f for f in os.listdir('.') if f.startswith('temp_video') or f.startswith('temp_trimmed_subs')]
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise Exception(f"Failed to download/trim video: {str(e)}")
    
    def _trim_subtitle_file(self, input_srt, output_srt, start_seconds, end_seconds):
        """Trim subtitle file to match video segment"""
        try:
            with open(input_srt, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple SRT parsing and trimming
            blocks = content.strip().split('\n\n')
            trimmed_blocks = []
            counter = 1
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    try:
                        time_line = lines[1]
                        start_time_str, end_time_str = time_line.split(' --> ')
                        
                        sub_start = self._srt_time_to_seconds(start_time_str)
                        sub_end = self._srt_time_to_seconds(end_time_str)
                        
                        # Check if subtitle overlaps with our trim range
                        if sub_end > start_seconds and sub_start < end_seconds:
                            # Adjust subtitle timing relative to new start
                            new_start = max(0, sub_start - start_seconds)
                            new_end = min(end_seconds - start_seconds, sub_end - start_seconds)
                            
                            if new_end > new_start:
                                new_start_str = self._seconds_to_srt_time(new_start)
                                new_end_str = self._seconds_to_srt_time(new_end)
                                
                                new_block = f"{counter}\n{new_start_str} --> {new_end_str}\n" + '\n'.join(lines[2:])
                                trimmed_blocks.append(new_block)
                                counter += 1
                    except:
                        continue
            
            with open(output_srt, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(trimmed_blocks))
                
        except Exception as e:
            # If subtitle trimming fails, create empty file
            with open(output_srt, 'w', encoding='utf-8') as f:
                f.write("")
    
    def _srt_time_to_seconds(self, time_str):
        """Convert SRT time format to seconds"""
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    
    def _seconds_to_srt_time(self, seconds):
        """Convert seconds to SRT time format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')


def get_user_input(prompt, validator=None):
    """Get user input with optional validation"""
    while True:
        try:
            user_input = input(prompt).strip()
            if not user_input:
                print("Input cannot be empty. Please try again.")
                continue
            
            if validator:
                validator(user_input)
            
            return user_input
        
        except KeyboardInterrupt:
            print(f"\nGoodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {str(e)}")
            print("Please try again.")


def print_banner():
    """Print application banner"""
    print(f"\n{'='*50}")
    print(f"YOUTUBE VIDEO PROCESSOR")
    print(f"Stats • Trim • Subtitles • Download")
    print(f"{'='*50}")


def print_stats(stats):
    """Print video statistics in a formatted way"""
    print(f"\nVideo Information:")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Title: {stats['title']}")
    print(f"Duration: {stats['duration']} | Views: {stats['view_count']} | Likes: {stats['like_count']}")
    print(f"Channel: {stats['uploader']} | Upload Date: {stats['upload_date']}")
    if stats['has_subtitles']:
        print(f"Subtitles: Available")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def ask_yes_no(question):
    """Ask a yes/no question"""
    while True:
        answer = input(f"{question} (y/n): ").strip().lower()
        if answer in ['y', 'yes']:
            return True
        elif answer in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' or 'n'.")


def main():
    print_banner()
    
    processor = YouTubeProcessor()
    
    try:
        # Get YouTube URL
        print(f"\nStep 1: Enter YouTube URL")
        video_url = get_user_input(
            "URL: ",
            validator=processor.validate_url
        )
        
        # Fetch and display stats
        stats = processor.fetch_stats(video_url)
        print_stats(stats)
        
        # Ask if user wants to trim
        print(f"\nStep 2: Video Trimming (Duration: {stats['duration']})")
        if not ask_yes_no("Do you want to trim this video?"):
            print("Video stats displayed. Goodbye!")
            return
        
        # Get quality choice
        quality_format = processor.get_quality_choice()
        
        # Ask about subtitles
        subtitle_lang = None
        if stats['has_subtitles']:
            print(f"\nStep 3: Subtitles")
            print("This video has subtitles available!")
            if ask_yes_no("Add subtitles to your video?"):
                subtitle_lang = processor.select_subtitle_language()
                if not subtitle_lang:
                    print("No subtitle selected, continuing without subtitles.")
        
        # Get start time  
        print(f"\nStep 4: Set Time Range (Format: MM:SS or HH:MM:SS)")
        start_time = get_user_input(
            "Start time: ",
            validator=processor.parse_timestamp
        )
        
        # Get end time
        end_time = get_user_input(
            "End time: ",
            validator=lambda x: processor.validate_timestamps(start_time, x)
        )
        
        # Ask for custom filename (optional)
        print(f"\nStep 5: Output File")
        custom_filename = input("Custom filename (optional): ").strip()
        output_filename = custom_filename if custom_filename else None
        
        # Confirm before processing
        clip_duration = processor.parse_timestamp(end_time) - processor.parse_timestamp(start_time)
        clip_duration_formatted = processor._format_duration(clip_duration)
        
        print(f"\nSummary:")
        print(f"Video: {stats['title'][:50]}...")
        print(f"Trim: {start_time} to {end_time} ({clip_duration_formatted})")
        if subtitle_lang:
            print(f"Subtitles: {processor._get_language_name(subtitle_lang)}")
        print(f"Output: {output_filename or 'Auto-generated filename'}")
        
        if not ask_yes_no(f"\nProceed with processing?"):
            print("Operation cancelled.")
            return  
        
        # Process the video
        print(f"\nProcessing...")
        output_file = processor.download_and_trim(
            start_time, end_time, quality_format, subtitle_lang, output_filename
        )
        
        print(f"\nSUCCESS!")
        print(f"File saved: {output_file}")
        print(f"Duration: {clip_duration_formatted}")
        print(f"Location: {os.path.abspath(output_file)}")
        
    except KeyboardInterrupt:
        print(f"\nGoodbye!")
    except Exception as e:
        print(f"\nError: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
