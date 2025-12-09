import json
import boto3
import os
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from decimal import Decimal
import requests
from typing import Dict, List, Optional
import uuid
import base64
import io

# Setup logging first
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import matplotlib - will fail if not available (error visible in AWS console)
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for Lambda
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import numpy as np

# AWS clients
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime', region_name=os.environ['REGION'])
lambda_client = boto3.client('lambda')

# Environment variables
REGION = os.environ['REGION']
USERS_TABLE = os.environ['USERS_TABLE']
REPORTS_TABLE = os.environ['REPORTS_TABLE']
EMAIL_SENDER_FUNCTION = os.environ['EMAIL_SENDER_FUNCTION']

# DynamoDB tables
users_table = dynamodb.Table(USERS_TABLE)
reports_table = dynamodb.Table(REPORTS_TABLE)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

# ========================================
# XML PARSERS FOR DIFFERENT REPORT TYPES
# ========================================

def parse_ivr_xml(xml_content: str) -> Dict:
    """
    Parse IVR XML report with improved analysis for Maya Analytics
    
    IVR XML Structure:
    - Multiple time groupings: date__groupsobjects, time__groupsobjects, weekday__groupsobjects, etc.
    - Each group contains: period, type (total/group/object), metrics, transferred_to_specification
    - Key metrics: incoming_total_handled_by_ivr, incoming_connected, incoming_not_connected, durations
    - Dynamic transfer destinations in transferred_to_specification/dynamic_column
    
    NOTE: This parser handles reports with MULTIPLE IVR correctly.
    Uses findall() to collect all IVR and aggregates data from all of them.
    """
    try:
        logger.info("🔍 Parsing IVR XML report...")
        root = ET.fromstring(xml_content)
        
        # Collect data from different time groupings
        daily_data = []
        hourly_data = []
        total_data = {}
        transfer_destinations = {}
        
        # Parse daily data (date__groupsobjects) - handles multiple IVR
        for date_group in root.findall('.//date__groupsobjects'):
            period = date_group.find('period')
            group_type = date_group.find('type')
            
            if period is not None and group_type is not None:
                period_text = period.text
                type_text = group_type.text
                
                # Extract detailed metadata: names, identifiers, groups
                # Note: <name> contains full name (e.g., "Others/belal.darwish - Belal Darwish")
                full_name = get_text_value(date_group, 'name')  # Full name from XML
                grouping_name = get_text_value(date_group, 'grouping_name')
                object_identifier = get_text_value(date_group, 'object_identifier')
                group_names = get_text_value(date_group, 'group_names')
                depth_in_hierarchy = get_text_value(date_group, 'depth_in_hierarchy')
                
                # Extract metrics
                data_point = {
                    'period': period_text,  # Specific date from XML (e.g., "2024-01-15", "15/01/2024")
                    'type': type_text,  # total/group/object
                    'name': full_name,  # Full name (e.g., "Others/belal.darwish - Belal Darwish")
                    'grouping_name': grouping_name,  # Name of the IVR function
                    'object_identifier': object_identifier,  # Unique identifier
                    'group_names': group_names,  # Names of parent groups
                    'depth_in_hierarchy': depth_in_hierarchy,  # Hierarchy level
                    'total_handled': get_int_value(date_group, 'incoming_total_handled_by_ivr'),
                    'connected': get_int_value(date_group, 'incoming_connected'),
                    'not_connected': get_int_value(date_group, 'incoming_not_connected'),
                    'avg_duration': get_int_value(date_group, 'incoming_average_call_duration_for_ivr'),
                    'total_duration': get_int_value(date_group, 'incoming_total_call_duration_for_ivr'),
                    'failures': get_int_value(date_group, 'incoming_terminated_because_of_failure'),
                    'transfers': parse_transfer_destinations(date_group)
                }
                
                if type_text == 'total':
                    total_data = data_point
                elif type_text == 'group' and period_text != 'Total':
                    daily_data.append(data_point)
                elif type_text == 'object' and period_text != 'Total':
                    # Include object-level data (contains specific IVR function name)
                    daily_data.append(data_point)
                
                # Collect all transfer destinations
                if data_point['transfers']:
                    for dest, count in data_point['transfers'].items():
                        if dest not in transfer_destinations:
                            transfer_destinations[dest] = 0
                        transfer_destinations[dest] += count

        # Parse hourly data (time__groupsobjects) - only active hours with enhanced analysis
        for time_group in root.findall('.//time__groupsobjects'):
            period = time_group.find('period')
            group_type = time_group.find('type')
            
            if (period is not None and group_type is not None and 
                (group_type.text == 'group' or group_type.text == 'object') and period.text != 'Total'):
                
                total_handled = get_int_value(time_group, 'incoming_total_handled_by_ivr')
                connected = get_int_value(time_group, 'incoming_connected')
                not_connected = get_int_value(time_group, 'incoming_not_connected')
                avg_duration = get_int_value(time_group, 'incoming_average_call_duration_for_ivr')
                
                # Extract detailed metadata for hourly data
                full_name = get_text_value(time_group, 'name')  # Full name from XML
                grouping_name = get_text_value(time_group, 'grouping_name')
                object_identifier = get_text_value(time_group, 'object_identifier')
                group_names = get_text_value(time_group, 'group_names')
                
                hourly_data.append({
                    'period': period.text,  # Specific time from XML (e.g., "09:00", "10:00")
                    'name': full_name,
                    'grouping_name': grouping_name,
                    'object_identifier': object_identifier,
                    'group_names': group_names,
                    'total_handled': total_handled,
                    'connected': connected,
                    'not_connected': not_connected,
                    'avg_duration': avg_duration,
                    'connection_rate': calculate_percentage(connected, total_handled) if total_handled > 0 else 0,
                    'abandonment_rate': calculate_percentage(not_connected, total_handled) if total_handled > 0 else 0,
                    'transfers': parse_transfer_destinations(time_group),
                    'efficiency_score': calculate_hourly_efficiency(total_handled, connected, avg_duration)
                })

        # Parse weekday data with detailed metadata
        weekday_data = []
        for weekday_group in root.findall('.//weekday__groupsobjects'):
            period = weekday_group.find('period')
            group_type = weekday_group.find('type')
            
            if (period is not None and group_type is not None and 
                group_type.text == 'group' and period.text not in ['Total']):
                
                full_name = get_text_value(weekday_group, 'name')  # Full name from XML
                grouping_name = get_text_value(weekday_group, 'grouping_name')
                object_identifier = get_text_value(weekday_group, 'object_identifier')
                group_names = get_text_value(weekday_group, 'group_names')
                
                weekday_data.append({
                    'day': period.text,  # Specific day name from XML (e.g., "Monday", "Lunedì", "1")
                    'name': full_name,
                    'grouping_name': grouping_name,
                    'object_identifier': object_identifier,
                    'group_names': group_names,
                    'total_handled': get_int_value(weekday_group, 'incoming_total_handled_by_ivr'),
                    'connected': get_int_value(weekday_group, 'incoming_connected'),
                    'not_connected': get_int_value(weekday_group, 'incoming_not_connected'),
                    'avg_duration': get_int_value(weekday_group, 'incoming_average_call_duration_for_ivr'),
                    'connection_rate': calculate_percentage(
                        get_int_value(weekday_group, 'incoming_connected'),
                        get_int_value(weekday_group, 'incoming_total_handled_by_ivr')
                    )
                })

        # Calculate derived metrics with enhanced analysis
        connection_rate = calculate_percentage(total_data.get('connected', 0), total_data.get('total_handled', 0))
        abandonment_rate = calculate_percentage(total_data.get('not_connected', 0), total_data.get('total_handled', 0))
        
        # Advanced hourly analysis
        hourly_patterns = identify_critical_hours(hourly_data)
        
        # Enhanced temporal pattern analysis
        temporal_insights = analyze_temporal_patterns(daily_data, weekday_data)
        
        # Identify peak hours with efficiency scoring
        peak_hours = sorted(hourly_data, key=lambda x: x.get('efficiency_score', 0), reverse=True)[:3]
        
        # Most active day with enhanced metrics
        most_active_day = max(weekday_data, key=lambda x: x['total_handled']) if weekday_data else None
        
        # Collect all unique names, identifiers, and groups for detailed reporting
        unique_groups = set()
        unique_identifiers = set()
        unique_names = set()
        all_periods = []
        all_weekdays = []
        
        unique_full_names = set()  # Full names from <name> tag
        
        for day in daily_data:
            if day.get('name'):  # Full name from <name> tag
                unique_full_names.add(day['name'])
            if day.get('grouping_name'):
                unique_names.add(day['grouping_name'])
            if day.get('object_identifier'):
                unique_identifiers.add(day['object_identifier'])
            if day.get('group_names'):
                unique_groups.add(day['group_names'])
            if day.get('period'):
                all_periods.append(day['period'])
        
        for hour in hourly_data:
            if hour.get('name'):  # Full name from <name> tag
                unique_full_names.add(hour['name'])
            if hour.get('grouping_name'):
                unique_names.add(hour['grouping_name'])
            if hour.get('object_identifier'):
                unique_identifiers.add(hour['object_identifier'])
            if hour.get('group_names'):
                unique_groups.add(hour['group_names'])
        
        for weekday in weekday_data:
            if weekday.get('day'):
                all_weekdays.append(weekday['day'])
            if weekday.get('name'):  # Full name from <name> tag
                unique_full_names.add(weekday['name'])
            if weekday.get('grouping_name'):
                unique_names.add(weekday['grouping_name'])
            if weekday.get('object_identifier'):
                unique_identifiers.add(weekday['object_identifier'])
        
        logger.info(f"✅ IVR XML parsed successfully - {total_data.get('total_handled', 0)} total calls")
        logger.info(f"📋 Found {len(unique_full_names)} unique full names, {len(unique_identifiers)} identifiers, {len(unique_groups)} groups")
        
        return {
            'report_type': 'ivr',
            'period_range': determine_period_range(daily_data),
            'specific_details': {
                'unique_full_names': sorted(list(unique_full_names)),  # Full names from <name> tag
                'unique_ivr_names': sorted(list(unique_names)),  # From grouping_name
                'unique_object_identifiers': sorted(list(unique_identifiers)),
                'unique_group_names': sorted(list(unique_groups)),
                'all_periods': sorted(list(set(all_periods))),  # All specific dates found
                'all_weekdays': sorted(list(set(all_weekdays))),  # All specific days of week found
                'total_data': {
                    'name': total_data.get('name', ''),
                    'grouping_name': total_data.get('grouping_name', ''),
                    'object_identifier': total_data.get('object_identifier', ''),
                    'group_names': total_data.get('group_names', ''),
                }
            },
            'summary': {
                'total_calls': total_data.get('total_handled', 0),
                'connected_calls': total_data.get('connected', 0),
                'abandoned_calls': total_data.get('not_connected', 0),
                'connection_rate': connection_rate,
                'abandonment_rate': abandonment_rate,
                'avg_call_duration': total_data.get('avg_duration', 0),
                'total_call_duration': format_duration_minutes(total_data.get('total_duration', 0)),
                'system_failures': total_data.get('failures', 0),
                'operational_efficiency': hourly_patterns.get('average_efficiency', 0)
            },
            'daily_breakdown': daily_data,
            'hourly_analysis': {
                'active_hours': hourly_patterns.get('total_active_hours', 0),
                'peak_hours': peak_hours,
                'all_hourly_data': hourly_data,
                'critical_patterns': hourly_patterns,
                'dead_hours_count': len(hourly_patterns.get('dead_hours', [])),
                'optimal_hours_count': len(hourly_patterns.get('optimal_hours', []))
            },
            'weekday_analysis': weekday_data,
            'transfer_analysis': {
                'destinations': transfer_destinations,
                'most_popular_destination': max(transfer_destinations.items(), key=lambda x: x[1]) if transfer_destinations else None,
                'total_transfers': sum(transfer_destinations.values()) if transfer_destinations else 0,
                'transfer_distribution': calculate_transfer_distribution(transfer_destinations)
            },
            'temporal_insights': temporal_insights,
            'insights': {
                'most_active_day': most_active_day,
                'busiest_hours': [h['period'] for h in peak_hours],
                'service_quality': assess_service_quality(connection_rate, total_data.get('avg_duration', 0)),
                'efficiency_trend': temporal_insights.get('daily_trend', 'N/A'),
                'volatility_assessment': temporal_insights.get('volatility', 'N/A'),
                'weekend_performance': temporal_insights.get('weekend_vs_weekday', {})
            }
        }
        
    except ET.ParseError as e:
        logger.error(f"❌ XML Parse Error in IVR report: {str(e)}")
        raise Exception(f"Invalid XML format: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error parsing IVR XML: {str(e)}")
        raise Exception(f"IVR parsing failed: {str(e)}")

def parse_transfer_destinations(element) -> Dict[str, int]:
    """Parse dynamic transfer destinations from transferred_to_specification"""
    transfers = {}
    
    transferred_spec = element.find('transferred_to_specification')
    if transferred_spec is not None:
        for dynamic_col in transferred_spec.findall('dynamic_column'):
            column_name = dynamic_col.find('column_name')
            column_value = dynamic_col.find('column_value')
            
            if column_name is not None and column_value is not None:
                try:
                    # Clean up the destination name
                    dest_name = column_name.text.strip()
                    if dest_name.startswith('Connected to '):
                        dest_name = dest_name[13:]  # Remove "Connected to " prefix
                    
                    transfers[dest_name] = int(column_value.text)
                except (ValueError, AttributeError):
                    continue
    
    return transfers

def get_text_value(element, tag_name: str) -> str:
    """Safely extract text value from XML element"""
    child = element.find(tag_name)
    if child is not None and child.text:
        return child.text.strip()
    return ''

def get_int_value(element, tag_name: str) -> int:
    """Safely extract integer value from XML element"""
    child = element.find(tag_name)
    if child is not None and child.text:
        try:
            return int(child.text)
        except ValueError:
            return 0
    return 0

def calculate_hourly_efficiency(total_handled: int, connected: int, avg_duration: float) -> float:
    """Calculate efficiency score for an hour based on volume, success rate, and duration"""
    if total_handled == 0:
        return 0.0
    
    # Volume weight (more calls = better, max score at 10+ calls)
    volume_score = min(total_handled / 10, 1.0) * 30
    
    # Connection rate weight (higher connection rate = better)
    connection_score = (connected / total_handled) * 50
    
    # Duration efficiency (shorter duration = better, optimal around 10-15 seconds)
    if 8 <= avg_duration <= 20:
        duration_score = 20  # Optimal range
    elif avg_duration < 8:
        duration_score = 15  # Too fast, might be hang-ups
    elif avg_duration <= 30:
        duration_score = 10  # Acceptable but slow
    else:
        duration_score = 5   # Too slow
    
    return round(volume_score + connection_score + duration_score, 1)

def identify_critical_hours(hourly_data: List[Dict]) -> Dict:
    """Identify critical time patterns from hourly data"""
    if not hourly_data:
        return {}
    
    # Sort by abandonment rate to find critical hours
    critical_hours = [h for h in hourly_data if h.get('abandonment_rate', 0) > 50]
    dead_hours = [h for h in hourly_data if h.get('total_handled', 0) == 0]
    optimal_hours = [h for h in hourly_data if h.get('connection_rate', 0) >= 90 and h.get('total_handled', 0) > 0]
    
    # Find peak efficiency hours
    efficiency_sorted = sorted(hourly_data, key=lambda x: x.get('efficiency_score', 0), reverse=True)
    peak_efficiency = efficiency_sorted[:3] if len(efficiency_sorted) >= 3 else efficiency_sorted
    
    return {
        'critical_hours': critical_hours,
        'dead_hours': dead_hours, 
        'optimal_hours': optimal_hours,
        'peak_efficiency': peak_efficiency,
        'total_active_hours': len([h for h in hourly_data if h.get('total_handled', 0) > 0]),
        'average_efficiency': round(sum(h.get('efficiency_score', 0) for h in hourly_data) / len(hourly_data), 1) if hourly_data else 0
    }

def analyze_temporal_patterns(daily_breakdown: List[Dict], weekday_analysis: List[Dict]) -> Dict:
    """Advanced temporal pattern analysis"""
    patterns = {}
    
    # Daily trend analysis
    if daily_breakdown:
        daily_volumes = [d.get('total_handled', 0) for d in daily_breakdown if d.get('type') == 'group']
        if len(daily_volumes) > 1:
            # Calculate trend
            trend = "crescente" if daily_volumes[-1] > daily_volumes[0] else "decrescente" if daily_volumes[-1] < daily_volumes[0] else "stabile"
            volatility = calculate_volatility(daily_volumes)
            patterns['daily_trend'] = trend
            patterns['volatility'] = volatility
            patterns['peak_day'] = max(daily_breakdown, key=lambda x: x.get('total_handled', 0)) if daily_breakdown else None
    
    # Weekly pattern analysis
    if weekday_analysis:
        weekend_performance = [d for d in weekday_analysis if d.get('day', '').lower() in ['saturday', 'sunday', 'sabato', 'domenica']]
        weekday_performance = [d for d in weekday_analysis if d not in weekend_performance]
        
        patterns['weekend_vs_weekday'] = {
            'weekend_avg': round(sum(w.get('total_handled', 0) for w in weekend_performance) / max(len(weekend_performance), 1), 1),
            'weekday_avg': round(sum(w.get('total_handled', 0) for w in weekday_performance) / max(len(weekday_performance), 1), 1),
            'most_active_weekday': max(weekday_analysis, key=lambda x: x.get('total_handled', 0)) if weekday_analysis else None
        }
    
    return patterns

def calculate_volatility(values: List[int]) -> str:
    """Calculate volatility description from a list of values"""
    if len(values) < 2:
        return "insufficienti dati"
    
    mean_val = sum(values) / len(values)
    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
    std_dev = variance ** 0.5
    coefficient_of_variation = (std_dev / mean_val) * 100 if mean_val > 0 else 0
    
    if coefficient_of_variation < 15:
        return "stabile"
    elif coefficient_of_variation < 30:
        return "moderata"
    else:
        return "alta"

def calculate_percentage(numerator: int, denominator: int) -> float:
    """Calculate percentage with safe division"""
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)

def format_duration_minutes(seconds: int) -> str:
    """Convert seconds to minutes:seconds format"""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}m {remaining_seconds}s"

def determine_period_range(daily_data: List[Dict]) -> str:
    """Determine the date range from daily data"""
    if not daily_data:
        return "N/A"
    
    dates = []
    for day in daily_data:
        period = day.get('period', '')
        if '/' in period and period != 'Total':
            dates.append(period.split()[0])  # Get just the date part
    
    if not dates:
        return "N/A"
    
    dates.sort()
    if len(dates) == 1:
        return dates[0]
    return f"{dates[0]} - {dates[-1]}"

def calculate_transfer_distribution(transfer_destinations: Dict[str, int]) -> Dict[str, float]:
    """Calculate percentage distribution of transfers"""
    if not transfer_destinations:
        return {}
    
    total_transfers = sum(transfer_destinations.values())
    if total_transfers == 0:
        return {}
    
    return {dest: round((count / total_transfers) * 100, 1) 
            for dest, count in transfer_destinations.items()}

def assess_service_quality(connection_rate: float, avg_duration: float) -> str:
    """Assess service quality based on metrics"""
    if connection_rate >= 90 and avg_duration <= 15:
        return "Eccellente"
    elif connection_rate >= 80 and avg_duration <= 20:
        return "Buona"
    elif connection_rate >= 70:
        return "Accettabile"
    else:
        return "Necessita miglioramenti"

# ========================================
# ACD (AUTOMATIC CALL DISTRIBUTION) PARSER
# ========================================

def parse_acd_xml(xml_content: str) -> Dict:
    """
    Parse ACD XML report with comprehensive call center analysis
    
    ACD XML Structure:
    - Key metrics: incoming_total, incoming_answered, incoming_unanswered, service_level
    - Queue metrics: queue_time, speed_of_answer, callbacks
    - Redirects: redirected calls, nightmode, overflow
    - Service levels: answered within time thresholds
    
    NOTE: This parser handles reports with MULTIPLE ACD groups correctly.
    Uses findall() to collect all groups and aggregates data from all of them.
    """
    try:
        logger.info("🔍 Parsing ACD XML report...")
        root = ET.fromstring(xml_content)
        
        daily_data = []
        hourly_data = []
        total_data = {}
        answered_by_members = {}
        
        # Parse daily data (date__groupsobjects) - handles multiple ACD groups
        for date_group in root.findall('.//date__groupsobjects'):
            period = date_group.find('period')
            group_type = date_group.find('type')
            
            if period is not None and group_type is not None:
                period_text = period.text
                type_text = group_type.text
                
                # Extract detailed metadata: names, identifiers, groups
                # Note: <name> contains full name (e.g., "Others/belal.darwish - Belal Darwish")
                full_name = get_text_value(date_group, 'name')  # Full name from XML
                grouping_name = get_text_value(date_group, 'grouping_name')
                object_identifier = get_text_value(date_group, 'object_identifier')
                group_names = get_text_value(date_group, 'group_names')
                depth_in_hierarchy = get_text_value(date_group, 'depth_in_hierarchy')
                
                data_point = {
                    'period': period_text,  # Specific date/day/time from XML
                    'type': type_text,  # total/group/object
                    'name': full_name,  # Full name (e.g., "Others/belal.darwish - Belal Darwish")
                    'grouping_name': grouping_name,  # Name of the group/user/function
                    'object_identifier': object_identifier,  # Unique identifier
                    'group_names': group_names,  # Names of parent groups
                    'depth_in_hierarchy': depth_in_hierarchy,  # Hierarchy level
                    'incoming_total': get_int_value(date_group, 'incoming_total'),
                    'incoming_answered': get_int_value(date_group, 'incoming_answered'),
                    'incoming_unanswered': get_int_value(date_group, 'incoming_unanswered'),
                    'incoming_queue_closed': get_int_value(date_group, 'incoming_queue_closed'),
                    'incoming_callbacks_requested': get_int_value(date_group, 'incoming_callbacks_requested'),
                    'outgoing_callbacks_resolved': get_int_value(date_group, 'outgoing_callbacks_resolved'),
                    'incoming_total_redirected': get_int_value(date_group, 'incoming_total_redirected'),
                    'incoming_redirected_no_agents_owerflow': get_int_value(date_group, 'incoming_redirected_no_agents_owerflow'),
                    'incoming_redirected_queue_timeout': get_int_value(date_group, 'incoming_redirected_queue_timeout'),
                    'incoming_redirected_nightmode': get_int_value(date_group, 'incoming_redirected_nightmode'),
                    'avg_speed_of_answer': get_time_value(date_group, 'incoming_answered_average_queue_time'),
                    'avg_call_duration': get_time_value(date_group, 'incoming_answered_average_call_duration'),
                    'total_call_duration': get_time_value(date_group, 'incoming_answered_total_call_duration'),
                    'avg_queue_time_unanswered': get_time_value(date_group, 'incoming_unanswered_average_queue_time'),
                    'percent_answered': get_float_value(date_group, 'incoming_percent_answered'),
                    'percent_unanswered': get_float_value(date_group, 'incoming_percent_unanswered'),
                    'percent_redirected': get_float_value(date_group, 'incoming_percent_redirected'),
                    'service_level_20': get_float_value(date_group, 'incoming_service_level'),
                    'answered_within_20': get_int_value(date_group, 'incoming_answered_within_service_time'),
                    'unanswered_within_20': get_int_value(date_group, 'incoming_unanswered_within_service_time'),
                }
                
                if type_text == 'total':
                    total_data = data_point
                elif type_text == 'group' and period_text != 'Total':
                    daily_data.append(data_point)
                elif type_text == 'object' and period_text != 'Total':
                    # Include object-level data (contains specific ACD group name)
                    daily_data.append(data_point)
                
                # Parse answered by members (dynamic columns)
                answered_by_spec = date_group.find('incoming_answered_by_member_specification')
                if answered_by_spec is not None:
                    for dynamic_col in answered_by_spec.findall('dynamic_column'):
                        member_name = dynamic_col.find('column_name')
                        member_value = dynamic_col.find('column_value')
                        if member_name is not None and member_value is not None:
                            member = member_name.text.strip()
                            count = int(member_value.text) if member_value.text else 0
                            if member not in answered_by_members:
                                answered_by_members[member] = 0
                            answered_by_members[member] += count
        
        # Parse hourly data (time__groupsobjects)
        for time_group in root.findall('.//time__groupsobjects'):
            period = time_group.find('period')
            group_type = time_group.find('type')
            
            if (period is not None and group_type is not None and 
                (group_type.text == 'group' or group_type.text == 'object') and period.text != 'Total'):
                
                total_incoming = get_int_value(time_group, 'incoming_total')
                answered = get_int_value(time_group, 'incoming_answered')
                unanswered = get_int_value(time_group, 'incoming_unanswered')
                
                # Extract detailed metadata for hourly data
                full_name = get_text_value(time_group, 'name')  # Full name from XML
                grouping_name = get_text_value(time_group, 'grouping_name')
                object_identifier = get_text_value(time_group, 'object_identifier')
                group_names = get_text_value(time_group, 'group_names')
                
                hourly_data.append({
                    'period': period.text,  # Specific time from XML (e.g., "09:00", "10:00")
                    'name': full_name,
                    'grouping_name': grouping_name,
                    'object_identifier': object_identifier,
                    'group_names': group_names,
                    'incoming_total': total_incoming,
                    'incoming_answered': answered,
                    'incoming_unanswered': unanswered,
                    'answer_rate': calculate_percentage(answered, total_incoming) if total_incoming > 0 else 0,
                    'abandonment_rate': calculate_percentage(unanswered, total_incoming) if total_incoming > 0 else 0,
                    'avg_speed_of_answer': get_time_value(time_group, 'incoming_answered_average_queue_time'),
                    'avg_call_duration': get_time_value(time_group, 'incoming_answered_average_call_duration'),
                    'service_level': get_float_value(time_group, 'incoming_service_level'),
                })
        
        # Calculate derived metrics
        total_incoming = total_data.get('incoming_total', 0)
        total_answered = total_data.get('incoming_answered', 0)
        total_unanswered = total_data.get('incoming_unanswered', 0)
        answer_rate = calculate_percentage(total_answered, total_incoming)
        abandonment_rate = calculate_percentage(total_unanswered, total_incoming)
        service_level = total_data.get('service_level_20', 0)
        
        # Identify peak hours
        peak_hours = sorted(hourly_data, key=lambda x: x.get('incoming_total', 0), reverse=True)[:3]
        
        # Critical hours analysis
        critical_hours = [h for h in hourly_data if h.get('abandonment_rate', 0) > 50]
        optimal_hours = [h for h in hourly_data if h.get('answer_rate', 0) >= 90 and h.get('service_level', 0) >= 80]
        
        # Collect all unique names, identifiers, and groups for detailed reporting
        unique_groups = set()
        unique_identifiers = set()
        unique_names = set()
        all_periods = []
        
        unique_full_names = set()  # Full names from <name> tag
        
        for day in daily_data:
            if day.get('name'):  # Full name from <name> tag
                unique_full_names.add(day['name'])
            if day.get('grouping_name'):
                unique_names.add(day['grouping_name'])
            if day.get('object_identifier'):
                unique_identifiers.add(day['object_identifier'])
            if day.get('group_names'):
                unique_groups.add(day['group_names'])
            if day.get('period'):
                all_periods.append(day['period'])
        
        for hour in hourly_data:
            if hour.get('name'):  # Full name from <name> tag
                unique_full_names.add(hour['name'])
            if hour.get('grouping_name'):
                unique_names.add(hour['grouping_name'])
            if hour.get('object_identifier'):
                unique_identifiers.add(hour['object_identifier'])
            if hour.get('group_names'):
                unique_groups.add(hour['group_names'])
        
        logger.info(f"✅ ACD XML parsed successfully - {total_incoming} total calls")
        logger.info(f"📋 Found {len(unique_full_names)} unique full names, {len(unique_identifiers)} identifiers, {len(unique_groups)} groups")
        
        return {
            'report_type': 'acd',
            'period_range': determine_period_range(daily_data),
            'specific_details': {
                'unique_full_names': sorted(list(unique_full_names)),  # Full names from <name> tag
                'unique_grouping_names': sorted(list(unique_names)),  # From grouping_name
                'unique_object_identifiers': sorted(list(unique_identifiers)),
                'unique_group_names': sorted(list(unique_groups)),
                'all_periods': sorted(list(set(all_periods))),  # All specific dates/days found
                'total_data': {
                    'name': total_data.get('name', ''),
                    'grouping_name': total_data.get('grouping_name', ''),
                    'object_identifier': total_data.get('object_identifier', ''),
                    'group_names': total_data.get('group_names', ''),
                }
            },
            'summary': {
                'total_incoming_calls': total_incoming,
                'answered_calls': total_answered,
                'unanswered_calls': total_unanswered,
                'answer_rate': answer_rate,
                'abandonment_rate': abandonment_rate,
                'service_level_20s': service_level,
                'queue_closed_calls': total_data.get('incoming_queue_closed', 0),
                'callbacks_requested': total_data.get('incoming_callbacks_requested', 0),
                'callbacks_resolved': total_data.get('outgoing_callbacks_resolved', 0),
                'total_redirected': total_data.get('incoming_total_redirected', 0),
                'redirected_no_agents': total_data.get('incoming_redirected_no_agents_owerflow', 0),
                'redirected_timeout': total_data.get('incoming_redirected_queue_timeout', 0),
                'redirected_nightmode': total_data.get('incoming_redirected_nightmode', 0),
                'avg_speed_of_answer': total_data.get('avg_speed_of_answer', 0),
                'avg_call_duration': total_data.get('avg_call_duration', 0),
                'avg_queue_time_unanswered': total_data.get('avg_queue_time_unanswered', 0),
            },
            'daily_breakdown': daily_data,
            'hourly_analysis': {
                'all_hourly_data': hourly_data,
                'peak_hours': peak_hours,
                'critical_hours': critical_hours,
                'optimal_hours': optimal_hours,
                'active_hours': len([h for h in hourly_data if h.get('incoming_total', 0) > 0]),
            },
            'agent_analysis': {
                'answered_by_members': answered_by_members,
                'top_agents': sorted(answered_by_members.items(), key=lambda x: x[1], reverse=True)[:5] if answered_by_members else [],
            },
            'insights': {
                'service_quality': assess_service_quality(answer_rate, total_data.get('avg_speed_of_answer', 0)),
                'queue_efficiency': assess_queue_efficiency(service_level, total_data.get('avg_speed_of_answer', 0)),
                'peak_periods': [h['period'] for h in peak_hours],
            }
        }
        
    except ET.ParseError as e:
        logger.error(f"❌ XML Parse Error in ACD report: {str(e)}")
        raise Exception(f"Invalid XML format: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error parsing ACD XML: {str(e)}")
        raise Exception(f"ACD parsing failed: {str(e)}")

# ========================================
# USER PARSER
# ========================================

def parse_user_xml(xml_content: str) -> Dict:
    """
    Parse User XML report with comprehensive call center analysis
    
    NOTE: This parser handles reports with MULTIPLE users correctly.
    Uses findall() to collect all users and aggregates data from all of them.
    """
    try:
        logger.info("🔍 Parsing User XML report...")
        root = ET.fromstring(xml_content)
        
        daily_data = []
        hourly_data = []
        total_data = {}
        
        # Parse daily data (date__groupsobjects) - handles multiple users
        for date_group in root.findall('.//date__groupsobjects'):
            period = date_group.find('period')
            group_type = date_group.find('type')
            
            if period is not None and group_type is not None:
                period_text = period.text
                type_text = group_type.text
                
                # Extract detailed metadata: names, identifiers, groups
                # Note: <name> contains full name (e.g., "Others/belal.darwish - Belal Darwish")
                #       <grouping_name> may not always be present
                full_name = get_text_value(date_group, 'name')  # Full name from XML
                grouping_name = get_text_value(date_group, 'grouping_name')
                object_identifier = get_text_value(date_group, 'object_identifier')
                group_names = get_text_value(date_group, 'group_names')
                depth_in_hierarchy = get_text_value(date_group, 'depth_in_hierarchy')
                
                data_point = {
                    'period': period_text,  # Specific date from XML
                    'type': type_text,  # total/group/object
                    'name': full_name,  # Full name (e.g., "Others/belal.darwish - Belal Darwish")
                    'grouping_name': grouping_name,  # Grouping name (may be empty)
                    'object_identifier': object_identifier,  # Unique user identifier/number
                    'group_names': group_names,  # Names of groups the user belongs to
                    'depth_in_hierarchy': depth_in_hierarchy,  # Hierarchy level
                    'incoming_total': get_int_value(date_group, 'incoming_total'),
                    'incoming_external': get_int_value(date_group, 'incoming_from_external'),
                    'incoming_internal': get_int_value(date_group, 'incoming_from_internal'),
                    'incoming_from_queues': get_int_value(date_group, 'incoming_from_queues'),
                    'incoming_answered': get_int_value(date_group, 'incoming_answered'),
                    'incoming_unanswered': get_int_value(date_group, 'incoming_unanswered'),
                    'incoming_busy': get_int_value(date_group, 'incoming_busy'),
                    'incoming_total_redirected': get_int_value(date_group, 'incoming_total_redirected'),
                    'incoming_redirected_voicemail': get_int_value(date_group, 'incoming_redirected_to_voicemail'),
                    'incoming_redirected_other': get_int_value(date_group, 'incoming_redirected_to_other'),
                    'incoming_avg_speed_of_answer': get_time_value(date_group, 'incoming_answered_average_speed_of_answer'),
                    'incoming_avg_duration': get_time_value(date_group, 'incoming_answered_average_duration'),
                    'incoming_total_duration': get_time_value(date_group, 'incoming_total_duration'),
                    'outgoing_total': get_int_value(date_group, 'outgoing_total'),
                    'outgoing_external': get_int_value(date_group, 'outgoing_to_external'),
                    'outgoing_internal': get_int_value(date_group, 'outgoing_to_internal'),
                    'outgoing_answered': get_int_value(date_group, 'outgoing_answered'),
                    'outgoing_unanswered': get_int_value(date_group, 'outgoing_unanswered'),
                    'outgoing_busy': get_int_value(date_group, 'outgoing_busy'),
                    'outgoing_avg_duration': get_time_value(date_group, 'outgoing_answered_average_duration'),
                    'outgoing_total_duration': get_time_value(date_group, 'outgoing_answered_total_duration'),
                    'transferred_out': get_int_value(date_group, 'outgoing_transferred_out'),
                    'total_calls': get_int_value(date_group, 'total_calls'),
                    'total_calls_duration': get_time_value(date_group, 'total_calls_duration'),
                    'failures': get_int_value(date_group, 'failures'),
                    'percent_answered': get_float_value(date_group, 'incoming_percent_answered'),
                }
                
                if type_text == 'total':
                    total_data = data_point
                elif type_text == 'group' and period_text != 'Total':
                    daily_data.append(data_point)
                elif type_text == 'object' and period_text != 'Total':
                    # Include object-level data (contains specific user name like "Others/belal.darwish - Belal Darwish")
                    daily_data.append(data_point)
        
        # Find the actual user name from object elements (not from total/group)
        # Object elements contain the real user name (e.g., "Others/belal.darwish - Belal Darwish")
        user_name_from_object = None
        user_identifier_from_object = None
        for date_group in root.findall('.//date__groupsobjects'):
            group_type = date_group.find('type')
            name_elem = date_group.find('name')
            if group_type is not None and group_type.text == 'object':
                if name_elem is not None and name_elem.text and name_elem.text != 'Total':
                    user_name_from_object = name_elem.text
                identifier_elem = date_group.find('object_identifier')
                if identifier_elem is not None and identifier_elem.text:
                    user_identifier_from_object = identifier_elem.text
                if user_name_from_object:  # Found it, no need to continue
                    break
        
        # Also check other grouping types (month, period, quarter) for object elements
        if not user_name_from_object:
            for grouping_type in ['month__groupsobjects', 'period__groupsobjects', 'quarter__groupsobjects']:
                for group_elem in root.findall(f'.//{grouping_type}'):
                    group_type = group_elem.find('type')
                    name_elem = group_elem.find('name')
                    if group_type is not None and group_type.text == 'object':
                        if name_elem is not None and name_elem.text and name_elem.text != 'Total':
                            user_name_from_object = name_elem.text
                            identifier_elem = group_elem.find('object_identifier')
                            if identifier_elem is not None and identifier_elem.text:
                                user_identifier_from_object = identifier_elem.text
                            break
                if user_name_from_object:
                    break
        
        # Update total_data with actual user name if found
        if user_name_from_object:
            total_data['name'] = user_name_from_object
            if user_identifier_from_object:
                total_data['object_identifier'] = user_identifier_from_object
        
        # Parse hourly data
        for time_group in root.findall('.//time__groupsobjects'):
            period = time_group.find('period')
            group_type = time_group.find('type')
            
            if (period is not None and group_type is not None and 
                (group_type.text == 'group' or group_type.text == 'object') and period.text != 'Total'):
                
                total_incoming = get_int_value(time_group, 'incoming_total')
                answered = get_int_value(time_group, 'incoming_answered')
                
                # Extract detailed metadata for hourly data
                full_name = get_text_value(time_group, 'name')  # Full name from XML
                grouping_name = get_text_value(time_group, 'grouping_name')
                object_identifier = get_text_value(time_group, 'object_identifier')
                group_names = get_text_value(time_group, 'group_names')
                
                hourly_data.append({
                    'period': period.text,  # Specific time from XML
                    'name': full_name,
                    'grouping_name': grouping_name,
                    'object_identifier': object_identifier,
                    'group_names': group_names,
                    'incoming_total': total_incoming,
                    'incoming_answered': answered,
                    'incoming_unanswered': get_int_value(time_group, 'incoming_unanswered'),
                    'outgoing_total': get_int_value(time_group, 'outgoing_total'),
                    'outgoing_answered': get_int_value(time_group, 'outgoing_answered'),
                    'answer_rate': calculate_percentage(answered, total_incoming) if total_incoming > 0 else 0,
                    'incoming_avg_duration': get_time_value(time_group, 'incoming_answered_average_duration'),
                    'outgoing_avg_duration': get_time_value(time_group, 'outgoing_answered_average_duration'),
                })
        
        # Calculate metrics
        total_incoming = total_data.get('incoming_total', 0)
        total_answered = total_data.get('incoming_answered', 0)
        total_outgoing = total_data.get('outgoing_total', 0)
        answer_rate = calculate_percentage(total_answered, total_incoming)
        
        peak_hours = sorted(hourly_data, key=lambda x: x.get('incoming_total', 0) + x.get('outgoing_total', 0), reverse=True)[:3]
        
        # Collect all unique names, identifiers, and groups for detailed reporting
        unique_groups = set()
        unique_identifiers = set()
        unique_names = set()
        unique_full_names = set()  # Full names from <name> tag
        all_periods = []
        
        for day in daily_data:
            # Only add names that are actual user names (not "Total" or empty)
            day_name = day.get('name', '')
            if day_name and day_name != 'Total' and day_name.strip():
                # Prefer names that look like user names (contain "/" and " - " pattern like "Others/belal.darwish - Belal Darwish")
                if '/' in day_name and ' - ' in day_name:
                    unique_full_names.add(day_name)
                elif day_name != 'Total':
                    unique_full_names.add(day_name)
            if day.get('grouping_name'):
                unique_names.add(day['grouping_name'])
            if day.get('object_identifier'):
                unique_identifiers.add(day['object_identifier'])
            if day.get('group_names'):
                unique_groups.add(day['group_names'])
            if day.get('period'):
                all_periods.append(day['period'])
        
        for hour in hourly_data:
            # Only add names that are actual user names (not "Total" or empty)
            hour_name = hour.get('name', '')
            if hour_name and hour_name != 'Total' and hour_name.strip():
                # Prefer names that look like user names (contain "/" and " - " pattern)
                if '/' in hour_name and ' - ' in hour_name:
                    unique_full_names.add(hour_name)
                elif hour_name != 'Total':
                    unique_full_names.add(hour_name)
            if hour.get('grouping_name'):
                unique_names.add(hour['grouping_name'])
            if hour.get('object_identifier'):
                unique_identifiers.add(hour['object_identifier'])
            if hour.get('group_names'):
                unique_groups.add(hour['group_names'])
        
        # Also add the user name from total_data if it was found
        if total_data.get('name') and total_data.get('name') != 'Total':
            total_name = total_data.get('name', '')
            if '/' in total_name and ' - ' in total_name:
                unique_full_names.add(total_name)
            elif total_name != 'Total':
                unique_full_names.add(total_name)
        
        logger.info(f"✅ User XML parsed successfully - {total_incoming} incoming, {total_outgoing} outgoing")
        logger.info(f"📋 Found {len(unique_full_names)} unique full names, {len(unique_identifiers)} identifiers, {len(unique_groups)} groups")
        if user_name_from_object:
            logger.info(f"👤 User name extracted: {user_name_from_object}")
        
        return {
            'report_type': 'user',
            'period_range': determine_period_range(daily_data),
            'specific_details': {
                'unique_full_names': sorted(list(unique_full_names)),  # Full names from <name> tag
                'unique_user_names': sorted(list(unique_names)),  # From grouping_name
                'unique_user_identifiers': sorted(list(unique_identifiers)),
                'unique_group_names': sorted(list(unique_groups)),
                'all_periods': sorted(list(set(all_periods))),  # All specific dates found
                'total_data': {
                    'name': total_data.get('name', ''),
                    'grouping_name': total_data.get('grouping_name', ''),
                    'object_identifier': total_data.get('object_identifier', ''),
                    'group_names': total_data.get('group_names', ''),
                }
            },
            'summary': {
                'incoming_total': total_incoming,
                'incoming_external': total_data.get('incoming_external', 0),
                'incoming_internal': total_data.get('incoming_internal', 0),
                'incoming_from_queues': total_data.get('incoming_from_queues', 0),
                'incoming_answered': total_answered,
                'incoming_unanswered': total_data.get('incoming_unanswered', 0),
                'incoming_busy': total_data.get('incoming_busy', 0),
                'incoming_redirected': total_data.get('incoming_total_redirected', 0),
                'incoming_redirected_voicemail': total_data.get('incoming_redirected_voicemail', 0),
                'incoming_avg_speed_of_answer': total_data.get('incoming_avg_speed_of_answer', 0),
                'incoming_avg_duration': total_data.get('incoming_avg_duration', 0),
                'outgoing_total': total_outgoing,
                'outgoing_external': total_data.get('outgoing_external', 0),
                'outgoing_internal': total_data.get('outgoing_internal', 0),
                'outgoing_answered': total_data.get('outgoing_answered', 0),
                'outgoing_unanswered': total_data.get('outgoing_unanswered', 0),
                'outgoing_avg_duration': total_data.get('outgoing_avg_duration', 0),
                'transferred_out': total_data.get('transferred_out', 0),
                'total_calls': total_data.get('total_calls', 0),
                'total_duration': format_duration_minutes(total_data.get('total_calls_duration', 0)),
                'failures': total_data.get('failures', 0),
                'answer_rate': answer_rate,
            },
            'daily_breakdown': daily_data,
            'hourly_analysis': {
                'all_hourly_data': hourly_data,
                'peak_hours': peak_hours,
                'active_hours': len([h for h in hourly_data if (h.get('incoming_total', 0) + h.get('outgoing_total', 0)) > 0]),
            },
            'insights': {
                'call_activity': assess_call_activity(total_incoming, total_outgoing),
                'efficiency': assess_user_efficiency(answer_rate, total_data.get('incoming_avg_duration', 0)),
            }
        }
        
    except ET.ParseError as e:
        logger.error(f"❌ XML Parse Error in User report: {str(e)}")
        raise Exception(f"Invalid XML format: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error parsing User XML: {str(e)}")
        raise Exception(f"User parsing failed: {str(e)}")

# ========================================
# HUNTGROUP PARSER
# ========================================

def parse_huntgroup_xml(xml_content: str) -> Dict:
    """
    Parse HuntGroup XML report with comprehensive call center analysis
    
    NOTE: This parser handles reports with MULTIPLE HuntGroups correctly.
    Uses findall() to collect all groups and aggregates data from all of them.
    """
    try:
        logger.info("🔍 Parsing HuntGroup XML report...")
        root = ET.fromstring(xml_content)
        
        daily_data = []
        hourly_data = []
        total_data = {}
        
        # Parse daily data - handles multiple HuntGroups
        for date_group in root.findall('.//date__groupsobjects'):
            period = date_group.find('period')
            group_type = date_group.find('type')
            
            if period is not None and group_type is not None:
                period_text = period.text
                type_text = group_type.text
                
                # Extract detailed metadata: names, identifiers, groups
                # Note: <name> contains full name (e.g., "Others/belal.darwish - Belal Darwish")
                full_name = get_text_value(date_group, 'name')  # Full name from XML
                grouping_name = get_text_value(date_group, 'grouping_name')
                object_identifier = get_text_value(date_group, 'object_identifier')
                group_names = get_text_value(date_group, 'group_names')
                depth_in_hierarchy = get_text_value(date_group, 'depth_in_hierarchy')
                
                data_point = {
                    'period': period_text,  # Specific date from XML
                    'type': type_text,  # total/group/object
                    'name': full_name,  # Full name (e.g., "Others/belal.darwish - Belal Darwish")
                    'grouping_name': grouping_name,  # Name of the HuntGroup
                    'object_identifier': object_identifier,  # Unique HuntGroup identifier/number
                    'group_names': group_names,  # Names of parent groups
                    'depth_in_hierarchy': depth_in_hierarchy,  # Hierarchy level
                    'incoming_total': get_int_value(date_group, 'incoming_total'),
                    'answered_by_members': get_int_value(date_group, 'incoming_answered_by_huntgroup_members'),
                    'unanswered_by_members': get_int_value(date_group, 'incoming_unanswered_by_huntgroup_members'),
                    'sent_to_overflow': get_int_value(date_group, 'incoming_sent_to_overflow_number'),
                    'avg_speed_of_answer': get_time_value(date_group, 'incoming_answered_by_huntgroup_members_average_speed_of_answer'),
                    'avg_call_duration': get_time_value(date_group, 'incoming_answered_by_huntgroup_members_average_call_duration'),
                    'total_call_duration': get_time_value(date_group, 'incoming_answered_by_huntgroup_members_total_call_duration'),
                }
                
                if type_text == 'total':
                    total_data = data_point
                elif type_text == 'group' and period_text != 'Total':
                    daily_data.append(data_point)
                elif type_text == 'object' and period_text != 'Total':
                    # Include object-level data (contains specific HuntGroup name)
                    daily_data.append(data_point)
        
        # Parse hourly data
        for time_group in root.findall('.//time__groupsobjects'):
            period = time_group.find('period')
            group_type = time_group.find('type')
            
            if (period is not None and group_type is not None and 
                (group_type.text == 'group' or group_type.text == 'object') and period.text != 'Total'):
                
                total_incoming = get_int_value(time_group, 'incoming_total')
                answered = get_int_value(time_group, 'incoming_answered_by_huntgroup_members')
                
                # Extract detailed metadata for hourly data
                full_name = get_text_value(time_group, 'name')  # Full name from XML
                grouping_name = get_text_value(time_group, 'grouping_name')
                object_identifier = get_text_value(time_group, 'object_identifier')
                group_names = get_text_value(time_group, 'group_names')
                
                hourly_data.append({
                    'period': period.text,  # Specific time from XML
                    'name': full_name,
                    'grouping_name': grouping_name,
                    'object_identifier': object_identifier,
                    'group_names': group_names,
                    'incoming_total': total_incoming,
                    'answered_by_members': answered,
                    'unanswered_by_members': get_int_value(time_group, 'incoming_unanswered_by_huntgroup_members'),
                    'sent_to_overflow': get_int_value(time_group, 'incoming_sent_to_overflow_number'),
                    'answer_rate': calculate_percentage(answered, total_incoming) if total_incoming > 0 else 0,
                    'avg_speed_of_answer': get_time_value(time_group, 'incoming_answered_by_huntgroup_members_average_speed_of_answer'),
                    'avg_call_duration': get_time_value(time_group, 'incoming_answered_by_huntgroup_members_average_call_duration'),
                })
        
        # Calculate metrics
        total_incoming = total_data.get('incoming_total', 0)
        total_answered = total_data.get('answered_by_members', 0)
        total_unanswered = total_data.get('unanswered_by_members', 0)
        total_overflow = total_data.get('sent_to_overflow', 0)
        answer_rate = calculate_percentage(total_answered, total_incoming)
        overflow_rate = calculate_percentage(total_overflow, total_incoming)
        
        peak_hours = sorted(hourly_data, key=lambda x: x.get('incoming_total', 0), reverse=True)[:3]
        critical_hours = [h for h in hourly_data if h.get('answer_rate', 0) < 70]
        
        # Collect all unique names, identifiers, and groups for detailed reporting
        unique_groups = set()
        unique_identifiers = set()
        unique_names = set()
        all_periods = []
        
        unique_full_names = set()  # Full names from <name> tag
        
        for day in daily_data:
            if day.get('name'):  # Full name from <name> tag
                unique_full_names.add(day['name'])
            if day.get('grouping_name'):
                unique_names.add(day['grouping_name'])
            if day.get('object_identifier'):
                unique_identifiers.add(day['object_identifier'])
            if day.get('group_names'):
                unique_groups.add(day['group_names'])
            if day.get('period'):
                all_periods.append(day['period'])
        
        for hour in hourly_data:
            if hour.get('name'):  # Full name from <name> tag
                unique_full_names.add(hour['name'])
            if hour.get('grouping_name'):
                unique_names.add(hour['grouping_name'])
            if hour.get('object_identifier'):
                unique_identifiers.add(hour['object_identifier'])
            if hour.get('group_names'):
                unique_groups.add(hour['group_names'])
        
        logger.info(f"✅ HuntGroup XML parsed successfully - {total_incoming} total calls")
        logger.info(f"📋 Found {len(unique_full_names)} unique full names, {len(unique_identifiers)} identifiers, {len(unique_groups)} groups")
        
        return {
            'report_type': 'huntgroup',
            'period_range': determine_period_range(daily_data),
            'specific_details': {
                'unique_full_names': sorted(list(unique_full_names)),  # Full names from <name> tag
                'unique_huntgroup_names': sorted(list(unique_names)),  # From grouping_name
                'unique_object_identifiers': sorted(list(unique_identifiers)),
                'unique_group_names': sorted(list(unique_groups)),
                'all_periods': sorted(list(set(all_periods))),  # All specific dates found
                'total_data': {
                    'name': total_data.get('name', ''),
                    'grouping_name': total_data.get('grouping_name', ''),
                    'object_identifier': total_data.get('object_identifier', ''),
                    'group_names': total_data.get('group_names', ''),
                }
            },
            'summary': {
                'incoming_total': total_incoming,
                'answered_by_members': total_answered,
                'unanswered_by_members': total_unanswered,
                'sent_to_overflow': total_overflow,
                'answer_rate': answer_rate,
                'overflow_rate': overflow_rate,
                'avg_speed_of_answer': total_data.get('avg_speed_of_answer', 0),
                'avg_call_duration': total_data.get('avg_call_duration', 0),
                'total_call_duration': format_duration_minutes(total_data.get('total_call_duration', 0)),
            },
            'daily_breakdown': daily_data,
            'hourly_analysis': {
                'all_hourly_data': hourly_data,
                'peak_hours': peak_hours,
                'critical_hours': critical_hours,
                'active_hours': len([h for h in hourly_data if h.get('incoming_total', 0) > 0]),
            },
            'insights': {
                'distribution_efficiency': assess_distribution_efficiency(answer_rate, overflow_rate),
                'service_quality': assess_service_quality(answer_rate, total_data.get('avg_speed_of_answer', 0)),
            }
        }
        
    except ET.ParseError as e:
        logger.error(f"❌ XML Parse Error in HuntGroup report: {str(e)}")
        raise Exception(f"Invalid XML format: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error parsing HuntGroup XML: {str(e)}")
        raise Exception(f"HuntGroup parsing failed: {str(e)}")

# ========================================
# RULEBASED PARSER
# ========================================

def parse_rulebased_xml(xml_content: str) -> Dict:
    """
    Parse RuleBased XML report with comprehensive call center analysis
    
    NOTE: This parser handles reports with MULTIPLE RuleBased correctly.
    Uses findall() to collect all rulebases and aggregates data from all of them.
    """
    try:
        logger.info("🔍 Parsing RuleBased XML report...")
        root = ET.fromstring(xml_content)
        
        daily_data = []
        hourly_data = []
        total_data = {}
        transfer_destinations = {}
        
        # Parse daily data - handles multiple RuleBased
        for date_group in root.findall('.//date__groupsobjects'):
            period = date_group.find('period')
            group_type = date_group.find('type')
            
            if period is not None and group_type is not None:
                period_text = period.text
                type_text = group_type.text
                
                # Extract detailed metadata: names, identifiers, groups
                # Note: <name> contains full name (e.g., "Others/belal.darwish - Belal Darwish")
                full_name = get_text_value(date_group, 'name')  # Full name from XML
                grouping_name = get_text_value(date_group, 'grouping_name')
                object_identifier = get_text_value(date_group, 'object_identifier')
                group_names = get_text_value(date_group, 'group_names')
                depth_in_hierarchy = get_text_value(date_group, 'depth_in_hierarchy')
                
                data_point = {
                    'period': period_text,  # Specific date from XML
                    'type': type_text,  # total/group/object
                    'name': full_name,  # Full name (e.g., "Others/belal.darwish - Belal Darwish")
                    'grouping_name': grouping_name,  # Name of the RuleBased function
                    'object_identifier': object_identifier,  # Unique RuleBased identifier/number
                    'group_names': group_names,  # Names of parent groups
                    'depth_in_hierarchy': depth_in_hierarchy,  # Hierarchy level
                    'handled_by_rulebase': get_int_value(date_group, 'incoming_total_handled_by_rulebase'),
                    'connected': get_int_value(date_group, 'incoming_connected'),
                    'not_connected': get_int_value(date_group, 'incoming_not_connected'),
                    'failures': get_int_value(date_group, 'incoming_failure'),
                    'transfers': parse_transfer_destinations_rulebased(date_group)
                }
                
                if type_text == 'total':
                    total_data = data_point
                elif type_text == 'group' and period_text != 'Total':
                    daily_data.append(data_point)
                elif type_text == 'object' and period_text != 'Total':
                    # Include object-level data (contains specific RuleBased function name)
                    daily_data.append(data_point)
                
                # Collect transfer destinations
                if data_point['transfers']:
                    for dest, count in data_point['transfers'].items():
                        if dest not in transfer_destinations:
                            transfer_destinations[dest] = 0
                        transfer_destinations[dest] += count
        
        # Parse hourly data
        for time_group in root.findall('.//time__groupsobjects'):
            period = time_group.find('period')
            group_type = time_group.find('type')
            
            if (period is not None and group_type is not None and 
                (group_type.text == 'group' or group_type.text == 'object') and period.text != 'Total'):
                
                handled = get_int_value(time_group, 'incoming_total_handled_by_rulebase')
                connected = get_int_value(time_group, 'incoming_connected')
                
                # Extract detailed metadata for hourly data
                full_name = get_text_value(time_group, 'name')  # Full name from XML
                grouping_name = get_text_value(time_group, 'grouping_name')
                object_identifier = get_text_value(time_group, 'object_identifier')
                group_names = get_text_value(time_group, 'group_names')
                
                hourly_data.append({
                    'period': period.text,  # Specific time from XML
                    'name': full_name,
                    'grouping_name': grouping_name,
                    'object_identifier': object_identifier,
                    'group_names': group_names,
                    'handled_by_rulebase': handled,
                    'connected': connected,
                    'not_connected': get_int_value(time_group, 'incoming_not_connected'),
                    'connection_rate': calculate_percentage(connected, handled) if handled > 0 else 0,
                    'transfers': parse_transfer_destinations_rulebased(time_group),
                })
        
        # Calculate metrics
        total_handled = total_data.get('handled_by_rulebase', 0)
        total_connected = total_data.get('connected', 0)
        total_not_connected = total_data.get('not_connected', 0)
        connection_rate = calculate_percentage(total_connected, total_handled)
        
        peak_hours = sorted(hourly_data, key=lambda x: x.get('handled_by_rulebase', 0), reverse=True)[:3]
        critical_hours = [h for h in hourly_data if h.get('connection_rate', 0) < 70]
        
        # Collect all unique names, identifiers, and groups for detailed reporting
        unique_groups = set()
        unique_identifiers = set()
        unique_names = set()
        all_periods = []
        
        unique_full_names = set()  # Full names from <name> tag
        
        for day in daily_data:
            if day.get('name'):  # Full name from <name> tag
                unique_full_names.add(day['name'])
            if day.get('grouping_name'):
                unique_names.add(day['grouping_name'])
            if day.get('object_identifier'):
                unique_identifiers.add(day['object_identifier'])
            if day.get('group_names'):
                unique_groups.add(day['group_names'])
            if day.get('period'):
                all_periods.append(day['period'])
        
        for hour in hourly_data:
            if hour.get('name'):  # Full name from <name> tag
                unique_full_names.add(hour['name'])
            if hour.get('grouping_name'):
                unique_names.add(hour['grouping_name'])
            if hour.get('object_identifier'):
                unique_identifiers.add(hour['object_identifier'])
            if hour.get('group_names'):
                unique_groups.add(hour['group_names'])
        
        logger.info(f"✅ RuleBased XML parsed successfully - {total_handled} total handled")
        logger.info(f"📋 Found {len(unique_full_names)} unique full names, {len(unique_identifiers)} identifiers, {len(unique_groups)} groups")
        
        return {
            'report_type': 'rulebased',
            'period_range': determine_period_range(daily_data),
            'specific_details': {
                'unique_full_names': sorted(list(unique_full_names)),  # Full names from <name> tag
                'unique_rulebased_names': sorted(list(unique_names)),  # From grouping_name
                'unique_object_identifiers': sorted(list(unique_identifiers)),
                'unique_group_names': sorted(list(unique_groups)),
                'all_periods': sorted(list(set(all_periods))),  # All specific dates found
                'total_data': {
                    'name': total_data.get('name', ''),
                    'grouping_name': total_data.get('grouping_name', ''),
                    'object_identifier': total_data.get('object_identifier', ''),
                    'group_names': total_data.get('group_names', ''),
                }
            },
            'summary': {
                'handled_by_rulebase': total_handled,
                'connected': total_connected,
                'not_connected': total_not_connected,
                'connection_rate': connection_rate,
                'failures': total_data.get('failures', 0),
                'total_transfers': sum(transfer_destinations.values()) if transfer_destinations else 0,
            },
            'daily_breakdown': daily_data,
            'hourly_analysis': {
                'all_hourly_data': hourly_data,
                'peak_hours': peak_hours,
                'critical_hours': critical_hours,
                'active_hours': len([h for h in hourly_data if h.get('handled_by_rulebase', 0) > 0]),
            },
            'transfer_analysis': {
                'destinations': transfer_destinations,
                'most_popular_destination': max(transfer_destinations.items(), key=lambda x: x[1]) if transfer_destinations else None,
                'transfer_distribution': calculate_transfer_distribution(transfer_destinations),
            },
            'insights': {
                'routing_efficiency': assess_routing_efficiency(connection_rate, total_data.get('failures', 0)),
                'service_quality': assess_service_quality(connection_rate, 0),
            }
        }
        
    except ET.ParseError as e:
        logger.error(f"❌ XML Parse Error in RuleBased report: {str(e)}")
        raise Exception(f"Invalid XML format: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error parsing RuleBased XML: {str(e)}")
        raise Exception(f"RuleBased parsing failed: {str(e)}")

# ========================================
# HELPER FUNCTIONS FOR PARSING
# ========================================

def get_time_value(element, tag_name: str) -> int:
    """Safely extract time value in seconds from XML element"""
    child = element.find(tag_name)
    if child is not None and child.text:
        try:
            # Time values can be in format "HH:MM:SS" or just seconds
            time_str = child.text.strip()
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 3:  # HH:MM:SS
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:  # MM:SS
                    return int(parts[0]) * 60 + int(parts[1])
            return int(time_str)
        except (ValueError, AttributeError):
            return 0
    return 0

def get_float_value(element, tag_name: str) -> float:
    """Safely extract float value from XML element"""
    child = element.find(tag_name)
    if child is not None and child.text:
        try:
            return float(child.text)
        except ValueError:
            return 0.0
    return 0.0

def parse_transfer_destinations_rulebased(element) -> Dict[str, int]:
    """Parse dynamic transfer destinations from incoming_transferred_to_specification"""
    transfers = {}
    
    transferred_spec = element.find('incoming_transferred_to_specification')
    if transferred_spec is not None:
        for dynamic_col in transferred_spec.findall('dynamic_column'):
            column_name = dynamic_col.find('column_name')
            column_value = dynamic_col.find('column_value')
            
            if column_name is not None and column_value is not None:
                try:
                    dest_name = column_name.text.strip()
                    if dest_name.startswith('Transferred to '):
                        dest_name = dest_name[15:]  # Remove prefix
                    transfers[dest_name] = int(column_value.text)
                except (ValueError, AttributeError):
                    continue
    
    return transfers

def assess_queue_efficiency(service_level: float, avg_speed: int) -> str:
    """Assess queue efficiency based on service level and speed of answer"""
    if service_level >= 80 and avg_speed <= 20:
        return "Eccellente"
    elif service_level >= 70 and avg_speed <= 30:
        return "Buona"
    elif service_level >= 60:
        return "Accettabile"
    else:
        return "Necessita miglioramenti"

def assess_call_activity(incoming: int, outgoing: int) -> str:
    """Assess call activity level"""
    total = incoming + outgoing
    if total > 100:
        return "Alta attività"
    elif total > 50:
        return "Attività moderata"
    elif total > 10:
        return "Attività bassa"
    else:
        return "Attività minima"

def assess_user_efficiency(answer_rate: float, avg_duration: int) -> str:
    """Assess user efficiency"""
    if answer_rate >= 90 and avg_duration <= 180:
        return "Eccellente"
    elif answer_rate >= 80:
        return "Buona"
    elif answer_rate >= 70:
        return "Accettabile"
    else:
        return "Necessita miglioramenti"

def assess_distribution_efficiency(answer_rate: float, overflow_rate: float) -> str:
    """Assess distribution efficiency for hunt groups"""
    if answer_rate >= 85 and overflow_rate <= 10:
        return "Eccellente"
    elif answer_rate >= 75 and overflow_rate <= 15:
        return "Buona"
    elif answer_rate >= 65:
        return "Accettabile"
    else:
        return "Necessita miglioramenti"

def assess_routing_efficiency(connection_rate: float, failures: int) -> str:
    """Assess routing efficiency for rule-based routing"""
    if connection_rate >= 90 and failures == 0:
        return "Eccellente"
    elif connection_rate >= 80 and failures <= 2:
        return "Buona"
    elif connection_rate >= 70:
        return "Accettabile"
    else:
        return "Necessita miglioramenti"

# ========================================
# LEGACY PARSERS (KEPT FOR COMPATIBILITY)
# ========================================

def parse_trunk_xml(xml_content: str) -> Dict:
    """Parse Trunk XML report (placeholder)"""
    try:
        logger.info("🔍 Parsing Trunk XML report...")
        root = ET.fromstring(xml_content)
        
        return {
            'report_type': 'trunk',
            'message': 'Trunk analysis not implemented yet'
        }
        
    except Exception as e:
        logger.error(f"❌ Error parsing Trunk XML: {str(e)}")
        raise Exception(f"Trunk parsing failed: {str(e)}")

def parse_queue_xml(xml_content: str) -> Dict:
    """Parse Queue XML report - redirects to ACD parser"""
    return parse_acd_xml(xml_content)

def parse_ddi_xml(xml_content: str) -> Dict:
    """Parse DDI XML report (placeholder)"""
    try:
        logger.info("🔍 Parsing DDI XML report...")
        root = ET.fromstring(xml_content)
        
        return {
            'report_type': 'ddi',
            'message': 'DDI analysis not implemented yet'
        }
        
    except Exception as e:
        logger.error(f"❌ Error parsing DDI XML: {str(e)}")
        raise Exception(f"DDI parsing failed: {str(e)}")

# ========================================
# REPORT TYPE DETECTION
# ========================================

def detect_report_type(xml_content: str) -> str:
    """
    Detect the type of report based on XML structure (not element names, but actual structure)
    
    NOTE: This function works correctly even when a report contains MULTIPLE elements of the same type:
    - Multiple users in the same report → detected as 'user'
    - Multiple ACD groups in the same report → detected as 'acd'
    - Multiple IVR in the same report → detected as 'ivr'
    - Multiple HuntGroups in the same report → detected as 'huntgroup'
    - Multiple RuleBased in the same report → detected as 'rulebased'
    
    The detection uses .find() which searches the entire XML tree, so it finds indicators
    even if there are multiple occurrences. Reports should NOT be mixed (e.g., ACD + USER together).
    
    Returns: 'acd', 'user', 'ivr', 'huntgroup', 'rulebased', 'trunk', 'queue', 'ddi', or 'unknown'
    """
    try:
        root = ET.fromstring(xml_content)
        
        # ACD: Has queue-specific metrics like queue_closed, service_level, callbacks, queue_time
        # Unique ACD indicators: queue_closed, service_level, answered_within_service_time, 
        # callbacks_requested, answered_by_member_specification, queue_time metrics
        # Works with multiple ACD groups in the same report (finds any occurrence in the tree)
        has_acd_indicators = (
            root.find('.//incoming_queue_closed') is not None or
            root.find('.//incoming_service_level') is not None or
            root.find('.//incoming_answered_within_service_time') is not None or
            root.find('.//incoming_unanswered_within_service_time') is not None or
            root.find('.//incoming_callbacks_requested') is not None or
            root.find('.//outgoing_callbacks_resolved') is not None or
            root.find('.//incoming_answered_by_member_specification') is not None or
            root.find('.//incoming_answered_average_queue_time') is not None or
            root.find('.//incoming_unanswered_average_queue_time') is not None or
            root.find('.//incoming_redirected_no_agents_owerflow') is not None or
            root.find('.//incoming_redirected_queue_timeout') is not None or
            root.find('.//incoming_redirected_nightmode') is not None
        )
        
        # HUNTGROUP: Has huntgroup-specific metrics
        # Unique indicators: answered_by_huntgroup_members, sent_to_overflow_number
        # Works with multiple HuntGroups in the same report (finds any occurrence in the tree)
        has_huntgroup_indicators = (
            root.find('.//incoming_answered_by_huntgroup_members') is not None or
            root.find('.//incoming_unanswered_by_huntgroup_members') is not None or
            root.find('.//incoming_sent_to_overflow_number') is not None or
            root.find('.//incoming_answered_by_huntgroup_members_average_speed_of_answer') is not None
        )
        
        # RULEBASED: Has rulebase-specific metrics
        # Unique indicators: total_handled_by_rulebase, incoming_transferred_to_specification
        # Works with multiple RuleBased in the same report (finds any occurrence in the tree)
        has_rulebased_indicators = (
            root.find('.//incoming_total_handled_by_rulebase') is not None or
            root.find('.//incoming_transferred_to_specification') is not None or
            root.find('.//incoming_failure') is not None
        )
        
        # IVR: Has IVR-specific metrics
        # Unique indicators: total_handled_by_ivr, average_call_duration_for_ivr, terminated_because_of_failure
        # Works with multiple IVR in the same report (finds any occurrence in the tree)
        has_ivr_indicators = (
            root.find('.//incoming_total_handled_by_ivr') is not None or
            root.find('.//incoming_average_call_duration_for_ivr') is not None or
            root.find('.//incoming_total_call_duration_for_ivr') is not None or
            root.find('.//incoming_terminated_because_of_failure') is not None or
            (root.find('.//transferred_to_specification') is not None and 
             root.find('.//incoming_total_handled_by_ivr') is not None)
        )
        
        # USER: Has user-specific structure with incoming/outgoing split, external/internal, from_queues
        # Unique indicators: incoming_from_external, incoming_from_internal, incoming_from_queues,
        # outgoing_to_external, outgoing_to_internal, outgoing_transferred_out, total_calls (in/out)
        # Works with multiple users in the same report (finds any occurrence in the tree)
        # BUT: Must NOT have ACD, HUNTGROUP, RULEBASED, or IVR indicators
        has_user_indicators = (
            root.find('.//incoming_from_external') is not None or
            root.find('.//incoming_from_internal') is not None or
            root.find('.//incoming_from_queues') is not None or
            root.find('.//outgoing_to_external') is not None or
            root.find('.//outgoing_to_internal') is not None or
            root.find('.//outgoing_transferred_out') is not None or
            root.find('.//total_calls') is not None or
            root.find('.//total_calls_duration') is not None
        )
        
        # Detection logic with priority (most specific first)
        if has_acd_indicators:
            return 'acd'
        
        if has_huntgroup_indicators:
            return 'huntgroup'
        
        if has_rulebased_indicators:
            return 'rulebased'
        
        if has_ivr_indicators:
            return 'ivr'
        
        # USER detection: has user structure AND doesn't have other specific indicators
        if has_user_indicators and not (has_acd_indicators or has_huntgroup_indicators or 
                                       has_rulebased_indicators or has_ivr_indicators):
            return 'user'
            
        # Check for Trunk specific elements
        if (root.find('.//trunk') is not None or 
            root.find('.//sip_trunk') is not None):
            return 'trunk'
            
        # Check for Queue specific elements (fallback to ACD)
        if (root.find('.//queue') is not None or 
            root.find('.//queue_stats') is not None):
            return 'acd'  # Queue reports use ACD parser
            
        # Check for DDI specific elements  
        if (root.find('.//ddi') is not None or 
            root.find('.//direct_dial') is not None):
            return 'ddi'
        
        # If we have basic incoming/outgoing structure but no specific indicators, 
        # check if it looks like a user report by structure
        has_basic_structure = (
            root.find('.//incoming_total') is not None or
            root.find('.//outgoing_total') is not None
        )
        
        if has_basic_structure and not (has_acd_indicators or has_huntgroup_indicators or 
                                       has_rulebased_indicators or has_ivr_indicators):
            # Check if it has the user report structure pattern
            if (root.find('.//incoming_answered') is not None and 
                root.find('.//outgoing_answered') is not None):
                return 'user'
        
        logger.warning("⚠️ Unknown report type - defaulting to ACD")
        return 'acd'  # Default to ACD if uncertain
        
    except ET.ParseError as e:
        logger.error(f"❌ XML Parse Error in detection: {str(e)}")
        return 'unknown'
    except Exception as e:
        logger.error(f"❌ Error detecting report type: {str(e)}")
        return 'unknown'

# ========================================
# XML PROCESSING PIPELINE
# ========================================

def parse_xml_report(xml_content: str) -> Dict:
    """
    Main XML parsing function that routes to appropriate parser
    """
    if not xml_content or not xml_content.strip():
        raise Exception("Empty XML content provided")
    
    # Detect report type
    report_type = detect_report_type(xml_content)
    logger.info(f"📊 Detected report type: {report_type}")
    
    # Route to appropriate parser
    parsers = {
        'acd': parse_acd_xml,
        'user': parse_user_xml, 
        'ivr': parse_ivr_xml,
        'huntgroup': parse_huntgroup_xml,
        'rulebased': parse_rulebased_xml,
        'trunk': parse_trunk_xml,
        'queue': parse_queue_xml,  # Redirects to ACD
        'ddi': parse_ddi_xml
    }
    
    parser_func = parsers.get(report_type)
    if not parser_func:
        raise Exception(f"No parser available for report type: {report_type}")
    
    return parser_func(xml_content)

# ========================================
# CLAUDE INTEGRATION
# ========================================

def generate_insights_with_claude(parsed_data: Dict) -> str:
    """Generate human-readable insights using Claude AI"""
    try:
        logger.info("🤖 Generating insights with Claude...")
        
        # Create a structured prompt based on report type
        report_type = parsed_data.get('report_type', 'unknown')
        
        if report_type == 'acd':
            prompt = create_acd_analysis_prompt(parsed_data)
        elif report_type == 'user':
            prompt = create_user_analysis_prompt(parsed_data)
        elif report_type == 'ivr':
            prompt = create_ivr_analysis_prompt(parsed_data)
        elif report_type == 'huntgroup':
            prompt = create_huntgroup_analysis_prompt(parsed_data)
        elif report_type == 'rulebased':
            prompt = create_rulebased_analysis_prompt(parsed_data)
        else:
            prompt = create_generic_analysis_prompt(parsed_data)
        
        # Call Claude via Bedrock
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 2000,
                'temperature': 0.3,
                'messages': [
                    {
                        'role': 'user', 
                        'content': prompt
                    }
                ]
            })
        )
        
        response_body = json.loads(response['body'].read())
        insights = response_body['content'][0]['text']
        
        logger.info("✅ Claude insights generated successfully")
        return insights
        
    except Exception as e:
        logger.error(f"❌ Error generating Claude insights: {str(e)}")
        # Fallback to basic summary
        return generate_fallback_insights(parsed_data)

def create_ivr_analysis_prompt(data: Dict) -> str:
    """Create specialized prompt for IVR analysis with enhanced formatting and ultra-precise insights"""
    summary = data.get('summary', {})
    daily_breakdown = data.get('daily_breakdown', [])
    hourly_analysis = data.get('hourly_analysis', {})
    weekday_analysis = data.get('weekday_analysis', [])
    transfer_analysis = data.get('transfer_analysis', {})
    insights = data.get('insights', {})
    specific_details = data.get('specific_details', {})
    
    # Extract more detailed patterns for enhanced analysis
    peak_hours = hourly_analysis.get('peak_hours', [])
    all_hourly_data = hourly_analysis.get('all_hourly_data', [])
    most_active_day = insights.get('most_active_day', {})
    
    # Extract specific names, identifiers, dates, and weekdays
    full_names = specific_details.get('unique_full_names', [])  # Full names from <name> tag
    ivr_names = specific_details.get('unique_ivr_names', [])  # From grouping_name
    identifiers = specific_details.get('unique_object_identifiers', [])
    group_names = specific_details.get('unique_group_names', [])
    all_periods = specific_details.get('all_periods', [])
    all_weekdays = specific_details.get('all_weekdays', [])
    
    # Build specific details section - prioritize full names
    details_section = ""
    if full_names:
        details_section += f"\n- Nomi completi IVR analizzati: {', '.join(full_names)}\n"
    elif ivr_names:
        details_section += f"\n- Nomi IVR analizzati: {', '.join(ivr_names)}\n"
    if identifiers:
        details_section += f"- Identificatori/numeri funzione: {', '.join(identifiers)}\n"
    if group_names:
        details_section += f"- Gruppi di appartenenza: {', '.join(group_names)}\n"
    if all_periods:
        details_section += f"- Date specifiche nel report: {', '.join(all_periods[:10])}{'...' if len(all_periods) > 10 else ''}\n"
    if all_weekdays:
        details_section += f"- Giorni della settimana analizzati: {', '.join(all_weekdays)}\n"
    
    # Build entity names section - handle multiple IVR functions
    actual_ivr_names = [n for n in full_names if n and n != 'Total'] if full_names else []
    if not actual_ivr_names and ivr_names:
        actual_ivr_names = [n for n in ivr_names if n and n != 'Total']
    
    entities_section = ""
    if len(actual_ivr_names) == 1:
        entities_section = f"\n📞 FUNZIONE IVR ANALIZZATA: {actual_ivr_names[0]}\n"
    elif len(actual_ivr_names) > 1:
        entities_section = f"\n📞 FUNZIONI IVR ANALIZZATE ({len(actual_ivr_names)}):\n"
        for idx, name in enumerate(actual_ivr_names, 1):
            entities_section += f"   {idx}. {name}\n"
        entities_section += "\n⚠️ IMPORTANTE: Questo report contiene dati per MULTIPLE FUNZIONI IVR. Devi differenziare le analisi per ogni funzione quando possibile.\n"
    
    return f"""
Analizza questo report IVR per Setera Centralino e fornisci insights professionali ULTRA-DETTAGLIATI in italiano.
{entities_section}

⚠️ CRITICO - RICONOSCIMENTO DATI FILTRATI/PARZIALI:
I report possono essere pre-filtrati e contenere solo un sottoinsieme di dati (es: solo una funzione IVR, solo un periodo specifico, solo determinati tipi di chiamate).
- Se un dato è 0 o mancante, VERIFICA se il report è filtrato prima di generare alert
- NON generare alert su dati mancanti se il report è chiaramente filtrato
- Analizza SOLO i dati presenti nel report, non quelli assenti per filtri
- Se il report contiene solo un sottoinsieme di funzioni IVR o tipi di chiamate, concentrati su quello e non segnalare come criticità l'assenza di altri dati
- Genera alert SOLO su anomalie nei dati effettivamente presenti, non su dati mancanti per filtri

IMPORTANTE: 
- Se ci sono MULTIPLE FUNZIONI IVR nel report, DEVI differenziare le analisi per ogni funzione
- Crea tabelle separate o colonne per funzione quando i dati lo permettono
- Menti esplicitamente i nomi delle funzioni IVR nelle analisi

IMPORTANTE: Devi includere SEMPRE nei tuoi insights i dettagli specifici reali estratti dai dati XML:
{details_section}

Devi menzionare esplicitamente:
- I nomi completi specifici delle funzioni IVR analizzate (es. "Others/belal.darwish - Belal Darwish", non generici)
- I numeri/identificatori delle funzioni quando disponibili
- Le date specifiche (non "alcuni giorni" ma le date reali come "15 gennaio", "20 febbraio", ecc.)
- I giorni della settimana specifici (non "alcuni giorni" ma "Lunedì", "Martedì", ecc.)
- I gruppi di appartenenza quando disponibili
- Gli orari specifici (non "mattina" ma "09:00", "10:00", ecc.)

📊 DATI GENERALI:
🗓️ Periodo: {data.get('period_range', 'N/A')}
📞 Chiamate totali: {summary.get('total_calls', 0)}
✅ Tasso di connessione: {summary.get('connection_rate', 0)}%
❌ Tasso di abbandono: {summary.get('abandonment_rate', 0)}%
⏱️ Durata media chiamate IVR: {summary.get('avg_call_duration', 0)} secondi
🎯 Qualità del servizio: {insights.get('service_quality', 'N/A')}

📈 BREAKDOWN GIORNALIERO DETTAGLIATO:
{json.dumps(daily_breakdown, indent=2) if daily_breakdown else 'Nessun dato giornaliero'}

🕐 ANALISI ORARIA COMPLETA:
Ore attive: {hourly_analysis.get('active_hours', 0)}
Ore di picco: {json.dumps(peak_hours, indent=2) if peak_hours else 'Nessun picco identificato'}
Tutti i dati orari: {json.dumps(all_hourly_data, indent=2) if all_hourly_data else 'Nessun dato orario'}

📅 PATTERN SETTIMANALI:
{json.dumps(weekday_analysis, indent=2) if weekday_analysis else 'Nessun pattern settimanale'}

📲 ANALISI TRASFERIMENTI:
Destinazioni: {json.dumps(transfer_analysis.get('destinations', {}), indent=2)}
Destinazione più popolare: {transfer_analysis.get('most_popular_destination', 'N/A')}

FORNISCI UN'ANALISI ULTRA-PRECISA E ULTRA-DETTAGLIATA con metriche avanzate IVR calcolate ESCLUSIVAMENTE dai dati reali:

🔍 1. PERFORMANCE SISTEMA IVR - METRICHE AVANZATE (calcolate dai dati reali)
   Crea una TABELLA con queste metriche IVR calcolate:
   
   | Metrica IVR | Valore | Target | Status | Calcolo |
   |-------------|--------|--------|--------|---------|
   | Tasso connessione | {summary.get('connection_rate', 0)}% | >90% | [calcola] | connected / total_handled |
   | Tasso abbandono | {summary.get('abandonment_rate', 0)}% | <10% | [calcola] | not_connected / total_handled |
   | Durata media chiamata | {summary.get('avg_call_duration', 0)}s | [analizza] | [calcola] | avg_duration dalle chiamate |
   | Tasso fallimenti sistema | {calculate_percentage(summary.get('system_failures', 0), summary.get('total_calls', 1))}% | <5% | [calcola] | failures / total_handled |
   | Efficienza operativa | {hourly_analysis.get('operational_efficiency', 0)}% | >80% | [calcola] | (connected × efficiency_score) / total |
   | Tasso trasferimenti | [calcola]% | [analizza] | [calcola] | total_transfers / total_handled |
   | Durata totale sistema | {summary.get('total_call_duration', 'N/A')} | [analizza] | [calcola] | sum di tutte le durate |
   
   • Analizza distribuzione oraria con dati precisi: identifica ESATTAMENTE:
     - Fasce orarie morte (0 chiamate) con orari specifici dai dati
     - Fasce orarie critiche (>50% abbandono) con orari precisi dai dati
     - Fasce orarie ottimali (>90% connessione) con orari precisi dai dati
     - Pattern durata chiamate per fascia oraria dai dati reali
   • Calcola efficienza operativa per ogni ora attiva dai dati orari
   • Crea SCHEMA ASCII "mappa termica" dei momenti critici della giornata

📊 2. ANALISI TEMPORALE ULTRA-DETTAGLIATA - TABELLE E SCHEMI
   Crea una TABELLA ORARIA IVR:
   
   | Ora | Totali | Connesse | Non Connesse | Durata Media | Tasso Connessione | Efficienza |
   |-----|--------|----------|--------------|--------------|-------------------|------------|
   [per ogni ora nei dati orari, inserisci i valori reali]
   
   Crea una TABELLA SETTIMANALE:
   
   | Giorno | Totali | Connesse | Abbandonate | Durata Media | Tasso Connessione | Analisi |
   |--------|--------|----------|-------------|--------------|-------------------|---------|
   [per ogni giorno nei dati weekday, inserisci i valori reali]
   
   Crea SCHEMA ASCII distribuzione oraria e settimanale
   
   • Per ogni giorno settimana: trend specifici e anomalie dai dati reali
   • Confronto performance giorni lavorativi vs weekend con calcoli
   • Identificazione "momento critico" settimana con orario preciso dai dati
   • Calcolo variabilità temporale: deviazione standard e coefficiente variazione
   • Previsioni operative basate su pattern identificati nei dati

🎯 3. INTELLIGENCE TRASFERIMENTI - ANALISI DETTAGLIATA
   Crea una TABELLA trasferimenti:
   
   | Destinazione | Quantità | % su Totali | % su Trasferimenti | Durata Media | Success Rate | Analisi |
   |--------------|----------|-------------|-------------------|--------------|--------------|---------|
   [per ogni destinazione nei dati transfer_analysis, inserisci valori reali]
   
   • Per ogni destinazione: efficienza, saturazione, timing ottimale dai dati
   • Analisi distribuzione carico: calcola deviazione standard tra destinazioni
   • Calcolo "transfer success rate" per fascia oraria dai dati orari
   • Identificazione opportunità load balancing: destinazioni sovraccariche vs sottoutilizzate
   • ROI stimato: (chiamate ottimizzate × valore medio) - costo implementazione

💡 4. ANALISI FALLIMENTI E ERRORI - METRICHE AVANZATE
   Crea una TABELLA fallimenti:
   
   | Tipo | Quantità | % su Totali | Trend | Causa Probabile | Azione Correttiva |
   |------|----------|-------------|-------|-----------------|-------------------|
   | Fallimenti sistema | {summary.get('system_failures', 0)} | [calcola] | [analizza] | [analizza] | [suggerisci] |
   | Chiamate non connesse | {summary.get('abandoned_calls', 0)} | [calcola] | [analizza] | [analizza] | [suggerisci] |
   
   • Analizza pattern fallimenti: correlazione con orari, giorni, volumi
   • Calcola costo fallimenti: (fallimenti × costo medio chiamata persa)

⚡ 5. RACCOMANDAZIONI OPERATIVE - PRIORITIZZATE CON DATI
   Crea una TABELLA priorità:
   
   | Priorità | Raccomandazione | Impatto Atteso | Dati Supporto | Timeline | ROI Stimato |
   |----------|----------------|----------------|---------------|----------|-------------|
   | 🔴 Alta | [specifica] | [quantifica] | [riferisci dati] | [specifica] | [calcola] |
   | 🟡 Media | [specifica] | [quantifica] | [riferisci dati] | [specifica] | [calcola] |
   | 🟢 Bassa | [specifica] | [quantifica] | [riferisci dati] | [specifica] | [calcola] |
   
   Ogni raccomandazione basata su dati reali:
   • Impatto quantificato: calcola % miglioramento atteso
   • Timeline implementazione: basata su complessità
   • ROI previsto: (beneficio - costo) / costo × 100

📈 6. DASHBOARD IVR - KPI CON VALORI REALI
   Crea una TABELLA KPI IVR completa:
   
   | KPI | Valore Attuale | Target | Gap | Trend | Alert Soglia |
   |-----|----------------|--------|-----|-------|--------------|
   | Tasso connessione | {summary.get('connection_rate', 0)}% | >90% | [calcola] | [analizza] | <85% |
   | Tasso abbandono | {summary.get('abandonment_rate', 0)}% | <10% | [calcola] | [analizza] | >15% |
   | Durata media | {summary.get('avg_call_duration', 0)}s | [analizza] | [calcola] | [analizza] | [soglia] |
   | Tasso fallimenti | [calcola]% | <5% | [calcola] | [analizza] | >8% |
   | Efficienza operativa | [calcola]% | >80% | [calcola] | [analizza] | <70% |
   | Tasso trasferimenti | [calcola]% | [analizza] | [calcola] | [analizza] | [soglia] |
   
   • Frequenza review: real-time per KPI critici, giornaliera per altri
   • Soglie alert: calcolate da deviazione standard dati storici

🎨 FORMATTAZIONE OBBLIGATORIA:
• MINIMO 4 TABELLE con dati reali (metriche, oraria, trasferimenti, KPI)
• MINIMO 2 SCHEMI/GRAFICI ASCII (distribuzione oraria, mappa termica)
• Sistema colori: 🟢 (ok), 🟡 (attenzione), 🔴 (critico)
• Tutti i calcoli mostrati esplicitamente
• Tutti i valori dai dati forniti, mai inventati

FOCUS PARTICOLARE SU PRECISION ANALYTICS:
- Calcoli esatti di costi operativi nascosti
- Identificazione di pattern sub-orari (es: primi 15 min vs ultimi 15 min dell'ora)
- Analisi della "customer journey" attraverso l'IVR
- Correlazioni tra eventi esterni (es: orari ufficio) e performance
- Suggerimenti per automazione intelligente con business case dettagliato

SCRIVI COME UN SENIOR OPERATIONS ANALYST che presenta all'utente:
• Dati actionable con ROI specifico
• Insights che collegano performance tecniche a risultati business
• Raccomandazioni che bilanciano customer experience e operational efficiency
• Linguaggio tecnico ma accessibile al management
"""

def create_acd_analysis_prompt(data: Dict) -> str:
    """Create specialized prompt for ACD (Automatic Call Distribution) analysis focused on call center performance"""
    summary = data.get('summary', {})
    daily_breakdown = data.get('daily_breakdown', [])
    hourly_analysis = data.get('hourly_analysis', {})
    agent_analysis = data.get('agent_analysis', {})
    insights = data.get('insights', {})
    specific_details = data.get('specific_details', {})
    
    peak_hours = hourly_analysis.get('peak_hours', [])
    critical_hours = hourly_analysis.get('critical_hours', [])
    optimal_hours = hourly_analysis.get('optimal_hours', [])
    top_agents = agent_analysis.get('top_agents', [])
    
    # Extract specific names, identifiers, dates
    full_names = specific_details.get('unique_full_names', [])  # Full names from <name> tag
    group_names = specific_details.get('unique_grouping_names', [])  # From grouping_name
    identifiers = specific_details.get('unique_object_identifiers', [])
    parent_groups = specific_details.get('unique_group_names', [])
    all_periods = specific_details.get('all_periods', [])
    
    # Build specific details section - prioritize full names
    details_section = ""
    if full_names:
        details_section += f"\n- Nomi completi gruppi ACD analizzati: {', '.join(full_names)}\n"
    elif group_names:
        details_section += f"\n- Nomi gruppi ACD analizzati: {', '.join(group_names)}\n"
    if identifiers:
        details_section += f"- Identificatori/numeri gruppo: {', '.join(identifiers)}\n"
    if parent_groups:
        details_section += f"- Gruppi padre: {', '.join(parent_groups)}\n"
    if all_periods:
        details_section += f"- Date specifiche nel report: {', '.join(all_periods[:10])}{'...' if len(all_periods) > 10 else ''}\n"
    
    # Build entity names section - handle multiple ACD groups
    actual_acd_names = [n for n in full_names if n and n != 'Total'] if full_names else []
    if not actual_acd_names and group_names:
        actual_acd_names = [n for n in group_names if n and n != 'Total']
    
    entities_section = ""
    if len(actual_acd_names) == 1:
        entities_section = f"\n📞 GRUPPO ACD ANALIZZATO: {actual_acd_names[0]}\n"
    elif len(actual_acd_names) > 1:
        entities_section = f"\n📞 GRUPPI ACD ANALIZZATI ({len(actual_acd_names)}):\n"
        for idx, name in enumerate(actual_acd_names, 1):
            entities_section += f"   {idx}. {name}\n"
        entities_section += "\n⚠️ IMPORTANTE: Questo report contiene dati per MULTIPLI GRUPPI ACD. Devi differenziare le analisi per ogni gruppo quando possibile.\n"
    
    return f"""
Analizza questo report ACD (Automatic Call Distribution) per Setera Centralino e fornisci insights ULTRA-DETTAGLIATI in italiano FOCALIZZATI ESCLUSIVAMENTE SULL'ANDAMENTO DEL CENTRALINO.
{entities_section}

⚠️ CRITICO - RICONOSCIMENTO DATI FILTRATI/PARZIALI:
I report possono essere pre-filtrati e contenere solo un sottoinsieme di dati (es: solo chiamate in arrivo, solo chiamate in uscita, solo un periodo specifico).
- Se un dato è 0 o mancante, VERIFICA se il report è filtrato prima di generare alert
- NON generare alert su dati mancanti se il report è chiaramente filtrato (es: se ci sono solo chiamate in arrivo e zero in uscita, è normale)
- Analizza SOLO i dati presenti nel report, non quelli assenti per filtri
- Se il report contiene solo un tipo di dati, concentrati su quello e non segnalare come criticità l'assenza dell'altro tipo
- Genera alert SOLO su anomalie nei dati effettivamente presenti, non su dati mancanti per filtri

IMPORTANTE: 
- Se ci sono MULTIPLI GRUPPI ACD nel report, DEVI differenziare le analisi per ogni gruppo
- Crea tabelle separate o colonne per gruppo quando i dati lo permettono
- Menti esplicitamente i nomi dei gruppi ACD nelle analisi

IMPORTANTE: Devi includere SEMPRE nei tuoi insights i dettagli specifici reali estratti dai dati XML:
{details_section}

Devi menzionare esplicitamente:
- I nomi completi specifici dei gruppi ACD analizzati (es. "Others/belal.darwish - Belal Darwish", non generici)
- I numeri/identificatori dei gruppi quando disponibili
- Le date specifiche (non "alcuni giorni" ma le date reali come "15 gennaio", "20 febbraio", ecc.)
- I gruppi padre quando disponibili
- Gli orari specifici (non "mattina" ma "09:00", "10:00", ecc.)
- I nomi specifici degli agenti quando disponibili nei dati

📊 DATI GENERALI CENTRALINO:
🗓️ Periodo: {data.get('period_range', 'N/A')}
📞 Chiamate totali in arrivo: {summary.get('total_incoming_calls', 0)}
✅ Chiamate risposte: {summary.get('answered_calls', 0)}
❌ Chiamate non risposte: {summary.get('unanswered_calls', 0)}
📈 Tasso di risposta: {summary.get('answer_rate', 0)}%
📉 Tasso di abbandono: {summary.get('abandonment_rate', 0)}%
⏱️ Service Level (20s): {summary.get('service_level_20s', 0)}%
⚡ Velocità media di risposta: {summary.get('avg_speed_of_answer', 0)}s
⏳ Durata media chiamata: {summary.get('avg_call_duration', 0)}s
🔄 Chiamate reindirizzate: {summary.get('total_redirected', 0)}
📞 Chiamate callback richieste: {summary.get('callbacks_requested', 0)}
✅ Callback risolti: {summary.get('callbacks_resolved', 0)}
🚫 Coda chiusa: {summary.get('queue_closed_calls', 0)}

📈 BREAKDOWN GIORNALIERO:
{json.dumps(daily_breakdown, indent=2) if daily_breakdown else 'Nessun dato giornaliero'}

🕐 ANALISI ORARIA CENTRALINO:
Ore attive: {hourly_analysis.get('active_hours', 0)}
Ore di picco: {json.dumps(peak_hours, indent=2) if peak_hours else 'Nessun picco'}
Ore critiche (abbandono >50%): {json.dumps(critical_hours, indent=2) if critical_hours else 'Nessuna ora critica'}
Ore ottimali (risposta >90%, SL >80%): {json.dumps(optimal_hours, indent=2) if optimal_hours else 'Nessuna ora ottimale'}

👥 ANALISI AGENTI:
Top 5 agenti: {json.dumps(top_agents, indent=2) if top_agents else 'Nessun dato agenti'}

FORNISCI UN'ANALISI ULTRA-PRECISA E ULTRA-DETTAGLIATA con metriche avanzate calcolate ESCLUSIVAMENTE dai dati reali:

🔍 1. PERFORMANCE CENTRALINO - METRICHE AVANZATE ACD (calcolate dai dati reali)
   Crea una TABELLA con queste metriche calcolate:
   
   | Metrica | Valore | Target | Status | Calcolo |
   |---------|--------|--------|--------|---------|
   | Service Level (20s) | {summary.get('service_level_20s', 0)}% | 80%+ | [calcola] | answered_within_20s / total_calls |
   | Velocità risposta media | {summary.get('avg_speed_of_answer', 0)}s | <20s | [calcola] | avg_queue_time delle chiamate risposte |
   | Tasso risposta | {summary.get('answer_rate', 0)}% | >85% | [calcola] | answered / total_incoming |
   | Tasso abbandono | {summary.get('abandonment_rate', 0)}% | <15% | [calcola] | unanswered / total_incoming |
   | Tasso reindirizzamento | {calculate_percentage(summary.get('total_redirected', 0), summary.get('total_incoming_calls', 1))}% | <10% | [calcola] | redirected / total_incoming |
   | Tasso callback richiesti | {calculate_percentage(summary.get('callbacks_requested', 0), summary.get('total_incoming_calls', 1))}% | [analizza] | [calcola] | callbacks_requested / total_incoming |
   | Tasso callback risolti | {calculate_percentage(summary.get('callbacks_resolved', 0), summary.get('callbacks_requested', 1)) if summary.get('callbacks_requested', 0) > 0 else 0}% | >80% | [calcola] | callbacks_resolved / callbacks_requested |
   | Tasso coda chiusa | {calculate_percentage(summary.get('queue_closed_calls', 0), summary.get('total_incoming_calls', 1))}% | [analizza] | [calcola] | queue_closed / total_incoming |
   | Tempo attesa medio non risposte | {summary.get('avg_queue_time_unanswered', 0)}s | [analizza] | [calcola] | avg_queue_time delle chiamate non risposte |
   | Durata media chiamata | {summary.get('avg_call_duration', 0)}s | [analizza] | [calcola] | avg_call_duration delle chiamate risposte |
   
   • Analizza la capacità del centralino di gestire il carico con questi calcoli specifici
   • Identifica colli di bottiglia operativi con orari precisi dai dati orari
   • Calcola il "costo dell'inefficienza": (chiamate perse × costo medio chiamata)
   • Valuta capacità picco vs media: (max_orario / media_oraria) × 100%

📊 2. ANALISI TEMPORALE CENTRALINO - TABELLE E SCHEMI
   Crea una TABELLA ORARIA con questi dati reali:
   
   | Ora | Chiamate | Risposte | Non risposte | SL% | Velocità risposta | Abbandono% |
   |-----|----------|----------|--------------|-----|-------------------|------------|
   [per ogni ora nei dati orari, inserisci i valori reali]
   
   Crea uno SCHEMA ASCII della distribuzione oraria:
   [grafico a barre ASCII con volume chiamate per ora]
   
   • Identifica fasce orarie critiche con dati precisi:
     - Ore sovraccarico: abbandono >50% (lista orari specifici)
     - Ore sottoutilizzo: volume < media - 50% (lista orari specifici)
     - Pattern di carico: picco alle [ora], minimo alle [ora]
   • Analizza distribuzione carico: calcola deviazione standard e variabilità
   • Confronto giorni: crea tabella comparativa con date specifiche

🎯 3. GESTIONE CODA E REINDIRIZZAMENTI - ANALISI DETTAGLIATA
   Crea una TABELLA dei reindirizzamenti:
   
   | Tipo Reindirizzamento | Quantità | % su Totali | % su Reindirizzati | Analisi |
   |----------------------|----------|-------------|-------------------|---------|
   | Mancanza agenti | {summary.get('redirected_no_agents', 0)} | [calcola] | [calcola] | [analizza causa] |
   | Timeout coda | {summary.get('redirected_timeout', 0)} | [calcola] | [calcola] | [analizza causa] |
   | Nightmode | {summary.get('redirected_nightmode', 0)} | [calcola] | [calcola] | [analizza causa] |
   | TOTALE | {summary.get('total_redirected', 0)} | [calcola] | 100% | [analisi complessiva] |
   
   • Valuta efficienza gestione code: (chiamate in coda / totali) × 100%
   • Analizza tempo medio in coda: confronta answered vs unanswered queue time
   • Identifica opportunità: calcola potenziale riduzione reindirizzamenti

💡 4. CALLBACK E RECUPERO CHIAMATE - METRICHE AVANZATE
   Crea una TABELLA callback:
   
   | Metrica | Valore | Calcolo | Analisi |
   |---------|--------|---------|---------|
   | Callback richiesti | {summary.get('callbacks_requested', 0)} | [dato reale] | [analizza trend] |
   | Callback risolti | {summary.get('callbacks_resolved', 0)} | [dato reale] | [analizza trend] |
   | Tasso successo callback | [calcola]% | resolved/requested | [confronta con target 80%] |
   | Chiamate perse potenzialmente recuperabili | [calcola] | unanswered - callbacks_requested | [opportunità] |
   | Tasso recupero chiamate | [calcola]% | (resolved + answered) / total | [efficacia sistema] |
   
   • Analizza efficacia sistema callback con calcoli specifici
   • Calcola ROI callback: (chiamate recuperate × valore medio) - costo gestione
   • Suggerisci miglioramenti con impatto quantificato

👥 5. ANALISI AGENTI - DISTRIBUZIONE PERFORMANCE
   Crea una TABELLA agenti (se disponibile):
   
   | Agente | Chiamate Risposte | % su Totali | Rank | Performance |
   |--------|-------------------|-------------|------|-------------|
   [per ogni agente nei dati answered_by_members, inserisci valori reali]
   
   • Analizza distribuzione carico agenti: calcola deviazione standard
   • Identifica top performer e agenti da supportare
   • Calcola efficienza per agente: (chiamate risposte / tempo disponibile)

⚡ 6. RACCOMANDAZIONI OPERATIVE - PRIORITIZZATE CON DATI
   Crea una TABELLA priorità:
   
   | Priorità | Raccomandazione | Impatto Atteso | Dati Supporto | Timeline |
   |----------|----------------|----------------|---------------|----------|
   | 🔴 Alta | [specifica] | [quantifica] | [riferisci dati] | [specifica] |
   | 🟡 Media | [specifica] | [quantifica] | [riferisci dati] | [specifica] |
   | 🟢 Bassa | [specifica] | [quantifica] | [riferisci dati] | [specifica] |
   
   Ogni raccomandazione deve essere basata su dati reali:
   • Ottimizzazioni staffing: basate su ore critiche identificate
   • Miglioramenti code: basati su tasso reindirizzamento
   • Alert performance: basati su soglie calcolate dai dati

📈 7. DASHBOARD CENTRALINO - KPI CON VALORI REALI
   Crea una TABELLA KPI completa:
   
   | KPI | Valore Attuale | Target | Gap | Trend | Alert Soglia |
   |-----|----------------|--------|-----|-------|--------------|
   | Service Level | {summary.get('service_level_20s', 0)}% | 80% | [calcola] | [analizza] | <75% |
   | Velocità risposta | {summary.get('avg_speed_of_answer', 0)}s | <20s | [calcola] | [analizza] | >25s |
   | Tasso risposta | {summary.get('answer_rate', 0)}% | >85% | [calcola] | [analizza] | <80% |
   | Tasso abbandono | {summary.get('abandonment_rate', 0)}% | <15% | [calcola] | [analizza] | >20% |
   | Tasso reindirizzamento | [calcola]% | <10% | [calcola] | [analizza] | >15% |
   | Tasso callback successo | [calcola]% | >80% | [calcola] | [analizza] | <70% |
   
   • Frequenza review: giornaliera per KPI critici, settimanale per altri
   • Soglie alert: calcolate da deviazione standard dei dati storici

🎨 FORMATTAZIONE OBBLIGATORIA:
• MINIMO 3 TABELLE con dati reali (non inventati)
• MINIMO 1 SCHEMA/GRAFICO ASCII (distribuzione oraria, trend, ecc.)
• Sistema colori: 🟢 (ok), 🟡 (attenzione), 🔴 (critico)
• Tutti i calcoli devono essere mostrati esplicitamente
• Tutti i valori devono provenire dai dati forniti, mai inventati

🎨 USA FORMATTAZIONE AVANZATA:
• Sistema di colori: 🟢 (eccellente), 🟡 (buono), 🔴 (critico)
• Trend indicators: 📈🚀 (miglioramento), 📊➡️ (stabile), 📉⚠️ (peggioramento)
• Box di insight: 🎯 opportunità, 🚨 urgenze, 💎 best practices

FOCUS ESCLUSIVO SULL'ANDAMENTO DEL CENTRALINO:
- Performance operativa del centralino
- Capacità di gestione del carico
- Efficienza nella distribuzione chiamate
- Qualità del servizio erogato
- Ottimizzazioni per migliorare l'efficienza

SCRIVI COME UN SENIOR CALL CENTER ANALYST focalizzato sull'andamento del centralino.
"""

def create_user_analysis_prompt(data: Dict) -> str:
    """Create specialized prompt for User report analysis focused on call center performance"""
    summary = data.get('summary', {})
    daily_breakdown = data.get('daily_breakdown', [])
    hourly_analysis = data.get('hourly_analysis', {})
    insights = data.get('insights', {})
    specific_details = data.get('specific_details', {})
    
    peak_hours = hourly_analysis.get('peak_hours', [])
    
    # Extract specific names, identifiers, dates
    full_names = specific_details.get('unique_full_names', [])  # Full names from <name> tag
    user_names = specific_details.get('unique_user_names', [])  # From grouping_name
    identifiers = specific_details.get('unique_user_identifiers', [])
    group_names = specific_details.get('unique_group_names', [])
    all_periods = specific_details.get('all_periods', [])
    
    # Build specific details section - prioritize full names
    details_section = ""
    if full_names:
        details_section += f"\n- Nomi completi utenti analizzati: {', '.join(full_names)}\n"
    elif user_names:
        details_section += f"\n- Nomi utenti analizzati: {', '.join(user_names)}\n"
    if identifiers:
        details_section += f"- Identificatori/numeri utente: {', '.join(identifiers)}\n"
    if group_names:
        details_section += f"- Gruppi di appartenenza: {', '.join(group_names)}\n"
    if all_periods:
        details_section += f"- Date specifiche nel report: {', '.join(all_periods[:10])}{'...' if len(all_periods) > 10 else ''}\n"
    
    # Build user name(s) for title/intro - handle multiple users
    # Filter out "Total" and group names, keep only actual user names
    actual_user_names = [n for n in full_names if n and n != 'Total' and '/' in n and ' - ' in n] if full_names else []
    
    # Extract display names (just the name part after the dash)
    user_display_names = []
    for full_name in actual_user_names:
        if " - " in full_name:
            display_name = full_name.split(" - ")[1]  # "Belal Darwish"
            if display_name not in user_display_names:
                user_display_names.append(display_name)
        elif full_name not in user_display_names:
            user_display_names.append(full_name)
    
    # Also check identifiers if no names found
    if not user_display_names and identifiers:
        user_display_names = list(identifiers)
    
    # Build intro text based on number of users
    if len(user_display_names) == 1:
        user_name_display = f" per l'utente {user_display_names[0]}"
    elif len(user_display_names) > 1:
        user_name_display = f" per gli utenti {', '.join(user_display_names)}"
    else:
        user_name_display = ""
    
    # Build users section for prompt
    users_section = ""
    if len(user_display_names) == 1:
        users_section = f"\n👤 UTENTE ANALIZZATO: {user_display_names[0]}\n"
    elif len(user_display_names) > 1:
        users_section = f"\n👥 UTENTI ANALIZZATI ({len(user_display_names)}):\n"
        for idx, name in enumerate(user_display_names, 1):
            users_section += f"   {idx}. {name}\n"
        users_section += "\nIMPORTANTE: Questo report contiene dati per MULTIPLI UTENTI. Devi differenziare le analisi per ogni utente quando possibile.\n"
    
    return f"""
Analizza questo report USER per Setera Centralino e fornisci insights ULTRA-DETTAGLIATI in italiano FOCALIZZATI ESCLUSIVAMENTE SULL'ANDAMENTO DEL CENTRALINO.

CRITICO - DEVI INIZIARE IL REPORT CON:
"Ecco un'analisi ultra-dettagliata focalizzata esclusivamente sull'andamento del centralino Setera{user_name_display} nel periodo [periodo specifico]"

{users_section}

⚠️ CRITICO - RICONOSCIMENTO DATI FILTRATI/PARZIALI:
I report possono essere pre-filtrati e contenere solo un sottoinsieme di dati (es: solo chiamate in arrivo, solo chiamate in uscita, solo un periodo specifico).
- Se un dato è 0 o mancante, VERIFICA se il report è filtrato prima di generare alert
- NON generare alert su dati mancanti se il report è chiaramente filtrato (es: se ci sono solo chiamate in uscita e zero in arrivo, è normale - il report è filtrato solo su chiamate in uscita)
- Analizza SOLO i dati presenti nel report, non quelli assenti per filtri
- Se il report contiene solo chiamate in arrivo (o solo in uscita), concentrati su quello e non segnalare come criticità l'assenza dell'altro tipo
- Genera alert SOLO su anomalie nei dati effettivamente presenti, non su dati mancanti per filtri

IMPORTANTE: 
- Se ci sono MULTIPLI UTENTI nel report, DEVI differenziare le analisi per ogni utente
- Crea tabelle separate o colonne per utente quando i dati lo permettono
- Menti esplicitamente i nomi degli utenti nelle analisi, non dire "Others" o "gruppo di utenti"
- Se c'è un solo utente, menziona sempre il suo nome completo (es. "Belal Darwish")

IMPORTANTE: Devi includere SEMPRE nei tuoi insights i dettagli specifici reali estratti dai dati XML:
{details_section}

Devi menzionare esplicitamente:
- ALL'INIZIO DEL REPORT: Il nome completo dell'utente di cui è fatto il report (es. "Belal Darwish" o "Others/belal.darwish - Belal Darwish")
- I nomi completi specifici degli utenti analizzati (es. "Others/belal.darwish - Belal Darwish", non generici)
- I numeri/identificatori degli utenti quando disponibili
- Le date specifiche (non "alcuni giorni" ma le date reali come "15 gennaio", "20 febbraio", ecc.)
- I gruppi di appartenenza quando disponibili
- Gli orari specifici (non "mattina" ma "09:00", "10:00", ecc.)

📊 DATI GENERALI CENTRALINO:
🗓️ Periodo: {data.get('period_range', 'N/A')}
📞 Chiamate in arrivo totali: {summary.get('incoming_total', 0)}
   - Esterne: {summary.get('incoming_external', 0)}
   - Interne: {summary.get('incoming_internal', 0)}
   - Da code: {summary.get('incoming_from_queues', 0)}
✅ Chiamate risposte: {summary.get('incoming_answered', 0)}
❌ Chiamate non risposte: {summary.get('incoming_unanswered', 0)}
📞 Chiamate occupato: {summary.get('incoming_busy', 0)}
🔄 Chiamate reindirizzate: {summary.get('incoming_redirected', 0)}
   - A segreteria: {summary.get('incoming_redirected_voicemail', 0)}
⚡ Velocità media risposta: {summary.get('incoming_avg_speed_of_answer', 0)}s
⏳ Durata media chiamata: {summary.get('incoming_avg_duration', 0)}s

📤 CHIAMATE IN USCITA:
📞 Chiamate totali: {summary.get('outgoing_total', 0)}
   - Esterne: {summary.get('outgoing_external', 0)}
   - Interne: {summary.get('outgoing_internal', 0)}
✅ Chiamate risposte: {summary.get('outgoing_answered', 0)}
❌ Chiamate non risposte: {summary.get('outgoing_unanswered', 0)}
⏳ Durata media: {summary.get('outgoing_avg_duration', 0)}s

📊 TOTALE ATTIVITÀ:
📞 Chiamate totali (in/out): {summary.get('total_calls', 0)}
⏱️ Durata totale: {summary.get('total_duration', 'N/A')}
🔄 Trasferimenti: {summary.get('transferred_out', 0)}
❌ Errori: {summary.get('failures', 0)}
📈 Tasso di risposta: {summary.get('answer_rate', 0)}%

📈 BREAKDOWN GIORNALIERO:
{json.dumps(daily_breakdown, indent=2) if daily_breakdown else 'Nessun dato giornaliero'}
{"⚠️ NOTA: I dati giornalieri contengono informazioni per più utenti. Analizza e differenzia per utente quando possibile." if len(user_display_names) > 1 else ""}

🕐 ANALISI ORARIA:
Ore di picco: {json.dumps(peak_hours, indent=2) if peak_hours else 'Nessun picco'}
Ore attive: {hourly_analysis.get('active_hours', 0)}
{"⚠️ NOTA: I dati orari contengono informazioni per più utenti. Crea analisi separate o comparativa per utente." if len(user_display_names) > 1 else ""}

FORNISCI UN'ANALISI ULTRA-PRECISA E ULTRA-DETTAGLIATA con questi elementi specifici:

🔍 1. PERFORMANCE CENTRALINO - UTILIZZO RISORSE CON METRICHE AVANZATE
   • Analizza l'utilizzo del centralino con dettagli specifici:
     - Volume chiamate in arrivo: {summary.get('incoming_total', 0)} (specifica per ogni giorno con date reali)
     - Volume chiamate in uscita: {summary.get('outgoing_total', 0)} (specifica per ogni giorno con date reali)
     - Bilanciamento traffico in/out con percentuali precise
     - Breakdown giornaliero dettagliato con date specifiche (non generiche)
   • Identifica pattern di utilizzo del centralino con orari precisi
   • Valuta l'efficienza operativa complessiva con calcoli specifici
   • Calcola il "costo dell'inefficienza" (chiamate perse = clienti insoddisfatti)
   • Analizza la variabilità giornaliera con confronti specifici tra giorni

📊 2. GESTIONE CHIAMATE IN ARRIVO - ANALISI ULTRA-DETTAGLIATA
   {"⚠️ SE CI SONO MULTIPLI UTENTI: Crea una TABELLA COMPARATIVA per utente con colonne separate per ogni utente" if len(user_display_names) > 1 else ""}
   
   • Analizza la capacità del centralino di gestire chiamate in arrivo:
     - Tasso di risposta: {summary.get('answer_rate', 0)}% (target: >85%) - specifica se sopra/sotto target
     - Chiamate da code: {summary.get('incoming_from_queues', 0)} - analizza l'impatto
     - Velocità di risposta: {summary.get('incoming_avg_speed_of_answer', 0)}s - confronta con target <20s
     - Chiamate esterne vs interne: {summary.get('incoming_external', 0)} vs {summary.get('incoming_internal', 0)}
     - Chiamate occupato: {summary.get('incoming_busy', 0)} - analizza cause e impatto
   {"• Se ci sono più utenti, confronta le performance tra utenti con una tabella comparativa" if len(user_display_names) > 1 else ""}
   • Identifica colli di bottiglia nella gestione chiamate con orari specifici
   • Valuta l'impatto dei reindirizzamenti: {summary.get('incoming_redirected', 0)} totali
     - A segreteria: {summary.get('incoming_redirected_voicemail', 0)}
     - Ad altri: {summary.get('incoming_redirected_other', 0)}
   • Analizza la distribuzione per tipo di chiamata (esterna/interna/da code) con percentuali

🎯 3. ANALISI TEMPORALE CENTRALINO - PATTERN ULTRA-DETTAGLIATI
   {"⚠️ SE CI SONO MULTIPLI UTENTI: Crea tabelle separate per utente o colonne per utente nelle tabelle temporali" if len(user_display_names) > 1 else ""}
   
   • Identifica fasce orarie critiche con orari precisi (es. "14:00-14:30", non "pomeriggio"):
     - Quando il centralino è più attivo (specifica orari esatti)
     - Pattern di carico durante la giornata con breakdown orario dettagliato
     - Correlazioni tra chiamate in/out per ogni fascia oraria
     - Picchi di attività con orari specifici e volumi precisi
   {"• Se ci sono più utenti, identifica pattern specifici per ogni utente (es. 'Belal Darwish è più attivo alle 14:00, mentre...')" if len(user_display_names) > 1 else ""}
   • Analizza breakdown giornaliero:
     - Per ogni giorno: volume totale, chiamate in/out, durate medie
     {"- Se ci sono più utenti: crea una tabella con colonne per utente mostrando i dati per giorno" if len(user_display_names) > 1 else ""}
     - Confronto tra giorni con variazioni percentuali
     - Identificazione di anomalie giornaliere
   • Suggerisci ottimizzazioni basate sui pattern temporali identificati
   • Calcola la distribuzione del carico nel tempo con metriche specifiche

💡 4. EFFICIENZA OPERATIVA - METRICHE AVANZATE USER (calcolate dai dati reali)
   {"⚠️ SE CI SONO MULTIPLI UTENTI: Crea una TABELLA COMPARATIVA con colonne per ogni utente" if len(user_display_names) > 1 else ""}
   
   Crea una TABELLA metriche efficienza{" (con colonne separate per ogni utente se ci sono più utenti)" if len(user_display_names) > 1 else ""}:
   
   {"| Metrica | " + " | ".join([f"{name}" for name in user_display_names]) + " | Totale | Target | Status |" if len(user_display_names) > 1 else ""}
   {"|---------|" + "|".join(["---" for _ in user_display_names]) + "|--------|--------|--------|" if len(user_display_names) > 1 else ""}
   | Metrica | In Arrivo | In Uscita | Totale | Target | Status | Calcolo |
   |---------|-----------|-----------|--------|--------|--------|---------|
   | Durata media | {summary.get('incoming_avg_duration', 0)}s | {summary.get('outgoing_avg_duration', 0)}s | [calcola] | [analizza] | [calcola] | avg_duration per tipo |
   | Tasso successo | [calcola]% | [calcola]% | [calcola] | >85% | [calcola] | answered / total |
   | Tasso occupato | {calculate_percentage(summary.get('incoming_busy', 0), summary.get('incoming_total', 1))}% | {calculate_percentage(summary.get('outgoing_busy', 0), summary.get('outgoing_total', 1))}% | [calcola] | <10% | [calcola] | busy / total |
   | Velocità risposta | {summary.get('incoming_avg_speed_of_answer', 0)}s | N/A | [calcola] | <20s | [calcola] | avg_speed_of_answer |
   | Durata totale | [calcola] | [calcola] | {summary.get('total_duration', 'N/A')} | [analizza] | [calcola] | sum durate |
   | Tasso trasferimenti | N/A | {calculate_percentage(summary.get('transferred_out', 0), summary.get('outgoing_total', 1))}% | [calcola] | [analizza] | [calcola] | transferred / outgoing |
   
   {"• Se ci sono più utenti, analizza le differenze di performance tra utenti e identifica best practices" if len(user_display_names) > 1 else ""}
   • Calcola metriche derivate dai dati reali:
     - Efficienza complessiva: (chiamate risolte / chiamate totali) × 100
     - Tasso occupazione: (durata totale / tempo disponibile) × 100
     - Produttività: chiamate totali / ore attive
     - Bilanciamento in/out: (incoming / outgoing) × 100
     - Tasso esterni vs interni: (external / internal) × 100
   • Identifica aree miglioramento con priorità e impatto quantificato dai dati

⚡ 5. RACCOMANDAZIONI PER IL CENTRALINO - PRECISE E MISURABILI
   Ogni raccomandazione deve essere specifica e actionable:
   • Ottimizzazioni operative specifiche con impatto quantificato
   • Miglioramenti nella gestione chiamate con timeline
   • Soglie di alert per performance con valori precisi
   • KPI da monitorare con target specifici
   • Priorità con matrice urgenza/impatto numerica
   • ROI stimato per ogni ottimizzazione proposta

📈 6. DASHBOARD CENTRALINO - KPI DETTAGLIATI
   • KPI chiave per monitorare con valori attuali e target:
     1. Tasso di risposta (target: >85%)
        Attuale: {summary.get('answer_rate', 0)}% - Specifica se sopra/sotto target e di quanto
     2. Velocità di risposta (target: <20s)
        Attuale: {summary.get('incoming_avg_speed_of_answer', 0)}s - Specifica se sopra/sotto target
     3. Volume chiamate in/out
        Attuale: {summary.get('incoming_total', 0)} in / {summary.get('outgoing_total', 0)} out
        Analizza lo sbilanciamento e suggerisci ottimizzazioni
     4. Durata media chiamate
        Attuale: {summary.get('incoming_avg_duration', 0)}s in / {summary.get('outgoing_avg_duration', 0)}s out
        Confronta con standard di settore e suggerisci ottimizzazioni
     5. Tasso di errore (target: minimizzare)
        Attuale: {summary.get('failures', 0)} errori su {summary.get('total_calls', 0)} chiamate
        Calcola percentuale e suggerisci azioni correttive
   • Frequenza di review consigliata per ogni KPI
   • Soglie di alert specifiche per ogni metrica

🎨 USA FORMATTAZIONE AVANZATA:
• Grafici ASCII dettagliati per distribuzioni e trend
• Tabelle comparative precise per performance giornaliere/orarie
• Sistema di colori: 🟢 (eccellente), 🟡 (buono), 🔴 (critico)
• Trend indicators: 📈🚀 (miglioramento), 📊➡️ (stabile), 📉⚠️ (peggioramento)
• Box di insight: 🎯 opportunità, 🚨 urgenze, 💎 best practices

FOCUS ESCLUSIVO SULL'ANDAMENTO DEL CENTRALINO con analisi ultra-dettagliata e specifica.
"""

def create_huntgroup_analysis_prompt(data: Dict) -> str:
    """Create specialized prompt for HuntGroup analysis focused on call center performance"""
    summary = data.get('summary', {})
    daily_breakdown = data.get('daily_breakdown', [])
    hourly_analysis = data.get('hourly_analysis', {})
    insights = data.get('insights', {})
    specific_details = data.get('specific_details', {})
    
    peak_hours = hourly_analysis.get('peak_hours', [])
    critical_hours = hourly_analysis.get('critical_hours', [])
    
    # Extract specific names, identifiers, dates
    full_names = specific_details.get('unique_full_names', [])  # Full names from <name> tag
    huntgroup_names = specific_details.get('unique_huntgroup_names', [])  # From grouping_name
    identifiers = specific_details.get('unique_object_identifiers', [])
    group_names = specific_details.get('unique_group_names', [])
    all_periods = specific_details.get('all_periods', [])
    
    # Build specific details section - prioritize full names
    details_section = ""
    if full_names:
        details_section += f"\n- Nomi completi HuntGroup analizzati: {', '.join(full_names)}\n"
    elif huntgroup_names:
        details_section += f"\n- Nomi HuntGroup analizzati: {', '.join(huntgroup_names)}\n"
    if identifiers:
        details_section += f"- Identificatori/numeri HuntGroup: {', '.join(identifiers)}\n"
    if group_names:
        details_section += f"- Gruppi di appartenenza: {', '.join(group_names)}\n"
    if all_periods:
        details_section += f"- Date specifiche nel report: {', '.join(all_periods[:10])}{'...' if len(all_periods) > 10 else ''}\n"
    
    # Build entity names section - handle multiple HuntGroups
    actual_hg_names = [n for n in full_names if n and n != 'Total'] if full_names else []
    if not actual_hg_names and huntgroup_names:
        actual_hg_names = [n for n in huntgroup_names if n and n != 'Total']
    
    entities_section = ""
    if len(actual_hg_names) == 1:
        entities_section = f"\n📞 HUNTGROUP ANALIZZATO: {actual_hg_names[0]}\n"
    elif len(actual_hg_names) > 1:
        entities_section = f"\n📞 HUNTGROUPS ANALIZZATI ({len(actual_hg_names)}):\n"
        for idx, name in enumerate(actual_hg_names, 1):
            entities_section += f"   {idx}. {name}\n"
        entities_section += "\n⚠️ IMPORTANTE: Questo report contiene dati per MULTIPLI HUNTGROUPS. Devi differenziare le analisi per ogni HuntGroup quando possibile.\n"
    
    return f"""
Analizza questo report HUNTGROUP per Setera Centralino e fornisci insights ULTRA-DETTAGLIATI in italiano FOCALIZZATI ESCLUSIVAMENTE SULL'ANDAMENTO DEL CENTRALINO.
{entities_section}

⚠️ CRITICO - RICONOSCIMENTO DATI FILTRATI/PARZIALI:
I report possono essere pre-filtrati e contenere solo un sottoinsieme di dati (es: solo un HuntGroup, solo un periodo specifico, solo determinati tipi di chiamate).
- Se un dato è 0 o mancante, VERIFICA se il report è filtrato prima di generare alert
- NON generare alert su dati mancanti se il report è chiaramente filtrato
- Analizza SOLO i dati presenti nel report, non quelli assenti per filtri
- Se il report contiene solo un sottoinsieme di HuntGroups o tipi di chiamate, concentrati su quello e non segnalare come criticità l'assenza di altri dati
- Genera alert SOLO su anomalie nei dati effettivamente presenti, non su dati mancanti per filtri

IMPORTANTE: 
- Se ci sono MULTIPLI HUNTGROUPS nel report, DEVI differenziare le analisi per ogni HuntGroup
- Crea tabelle separate o colonne per HuntGroup quando i dati lo permettono
- Menti esplicitamente i nomi degli HuntGroups nelle analisi

IMPORTANTE: Devi includere SEMPRE nei tuoi insights i dettagli specifici reali estratti dai dati XML:
{details_section}

Devi menzionare esplicitamente:
- I nomi completi specifici dei HuntGroup analizzati (es. "Others/belal.darwish - Belal Darwish", non generici)
- I numeri/identificatori dei HuntGroup quando disponibili
- Le date specifiche (non "alcuni giorni" ma le date reali come "15 gennaio", "20 febbraio", ecc.)
- I gruppi di appartenenza quando disponibili
- Gli orari specifici (non "mattina" ma "09:00", "10:00", ecc.)

📊 DATI GENERALI CENTRALINO:
🗓️ Periodo: {data.get('period_range', 'N/A')}
📞 Chiamate totali in arrivo: {summary.get('incoming_total', 0)}
✅ Risposte da membri gruppo: {summary.get('answered_by_members', 0)}
❌ Non risposte da membri: {summary.get('unanswered_by_members', 0)}
🔄 Inviate a overflow: {summary.get('sent_to_overflow', 0)}
📈 Tasso di risposta: {summary.get('answer_rate', 0)}%
📉 Tasso di overflow: {summary.get('overflow_rate', 0)}%
⚡ Velocità media risposta: {summary.get('avg_speed_of_answer', 0)}s
⏳ Durata media chiamata: {summary.get('avg_call_duration', 0)}s
⏱️ Durata totale: {summary.get('total_call_duration', 'N/A')}

📈 BREAKDOWN GIORNALIERO:
{json.dumps(daily_breakdown, indent=2) if daily_breakdown else 'Nessun dato giornaliero'}

🕐 ANALISI ORARIA CENTRALINO:
Ore di picco: {json.dumps(peak_hours, indent=2) if peak_hours else 'Nessun picco'}
Ore critiche (risposta <70%): {json.dumps(critical_hours, indent=2) if critical_hours else 'Nessuna ora critica'}
Ore attive: {hourly_analysis.get('active_hours', 0)}

FORNISCI UN'ANALISI ULTRA-PRECISA FOCALIZZATA SULL'ANDAMENTO DEL CENTRALINO:

🔍 1. PERFORMANCE CENTRALINO - METRICHE AVANZATE HUNTGROUP (calcolate dai dati reali)
   Crea una TABELLA con queste metriche HUNTGROUP calcolate:
   
   | Metrica HUNTGROUP | Valore | Target | Status | Calcolo |
   |-------------------|--------|--------|--------|---------|
   | Tasso risposta membri | {summary.get('answer_rate', 0)}% | >85% | [calcola] | answered_by_members / total |
   | Tasso overflow | {summary.get('overflow_rate', 0)}% | <10% | [calcola] | sent_to_overflow / total |
   | Velocità risposta | {summary.get('avg_speed_of_answer', 0)}s | <20s | [calcola] | avg_speed_of_answer |
   | Durata media chiamata | {summary.get('avg_call_duration', 0)}s | [analizza] | [calcola] | avg_call_duration |
   | Tasso non risposte membri | {calculate_percentage(summary.get('unanswered_by_members', 0), summary.get('incoming_total', 1))}% | <15% | [calcola] | unanswered_by_members / total |
   | Efficienza distribuzione | [calcola]% | >80% | [calcola] | (answered / total) × (1 - overflow_rate) |
   
   • Analizza efficienza distribuzione chiamate con calcoli specifici
   • Identifica quando centralino non gestisce carico: overflow >10% con orari precisi
   • Valuta capacità picco vs media: (max_orario / media_oraria) × 100%

📊 2. GESTIONE OVERFLOW - ANALISI DETTAGLIATA
   Crea una TABELLA overflow:
   
   | Metrica | Valore | % su Totali | Trend | Analisi | Azione |
   |---------|--------|-------------|-------|---------|--------|
   | Chiamate overflow | {summary.get('sent_to_overflow', 0)} | {summary.get('overflow_rate', 0)}% | [analizza] | [analizza causa] | [suggerisci] |
   | Chiamate risposte membri | {summary.get('answered_by_members', 0)} | [calcola]% | [analizza] | [analizza] | [suggerisci] |
   | Chiamate non risposte | {summary.get('unanswered_by_members', 0)} | [calcola]% | [analizza] | [analizza] | [suggerisci] |
   
   • Identifica pattern overflow con dati precisi dai dati orari
   • Suggerisci ottimizzazioni con impatto quantificato

🎯 3. ANALISI TEMPORALE - TABELLE E SCHEMI
   Crea una TABELLA ORARIA HUNTGROUP:
   
   | Ora | Totali | Risposte Membri | Non Risposte | Overflow | Tasso Risposta | Overflow% |
   |-----|--------|----------------|--------------|----------|----------------|-----------|
   [per ogni ora nei dati orari, inserisci i valori reali]
   
   Crea SCHEMA ASCII distribuzione oraria e overflow pattern
   
   • Identifica fasce orarie critiche con dati precisi dai dati orari
   • Analizza capacità gestione nel tempo: calcola variabilità e trend

💡 4. EFFICIENZA OPERATIVA - METRICHE AVANZATE
   Crea una TABELLA efficienza:
   
   | Metrica | Valore | Target | Gap | Analisi | Azione |
   |---------|--------|--------|-----|---------|--------|
   | Velocità risposta | {summary.get('avg_speed_of_answer', 0)}s | <20s | [calcola] | [analizza] | [suggerisci] |
   | Durata media | {summary.get('avg_call_duration', 0)}s | [analizza] | [calcola] | [analizza] | [suggerisci] |
   | Efficienza distribuzione | [calcola]% | >80% | [calcola] | [analizza] | [suggerisci] |
   
   • Valuta efficienza complessiva con calcoli dettagliati
   • Identifica aree miglioramento con priorità e impatto quantificato

⚡ 5. RACCOMANDAZIONI OPERATIVE - PRIORITIZZATE CON DATI
   Crea una TABELLA priorità:
   
   | Priorità | Raccomandazione | Impatto Atteso | Dati Supporto | Timeline | ROI |
   |----------|----------------|----------------|---------------|----------|-----|
   | 🔴 Alta | [specifica] | [quantifica] | [riferisci dati] | [specifica] | [calcola] |
   | 🟡 Media | [specifica] | [quantifica] | [riferisci dati] | [specifica] | [calcola] |
   | 🟢 Bassa | [specifica] | [quantifica] | [riferisci dati] | [specifica] | [calcola] |
   
   Ogni raccomandazione basata su dati reali

📈 6. DASHBOARD HUNTGROUP - KPI CON VALORI REALI
   Crea una TABELLA KPI completa:
   
   | KPI | Valore Attuale | Target | Gap | Trend | Alert Soglia |
   |-----|----------------|--------|-----|-------|--------------|
   | Tasso risposta | {summary.get('answer_rate', 0)}% | >85% | [calcola] | [analizza] | <80% |
   | Tasso overflow | {summary.get('overflow_rate', 0)}% | <10% | [calcola] | [analizza] | >15% |
   | Velocità risposta | {summary.get('avg_speed_of_answer', 0)}s | <20s | [calcola] | [analizza] | >25s |
   | Efficienza distribuzione | [calcola]% | >80% | [calcola] | [analizza] | <70% |

🎨 FORMATTAZIONE OBBLIGATORIA:
• MINIMO 3 TABELLE con dati reali (metriche, overflow, oraria)
• MINIMO 1 SCHEMA/GRAFICO ASCII (distribuzione oraria, overflow pattern)
• Sistema colori: 🟢 (ok), 🟡 (attenzione), 🔴 (critico)
• Tutti i calcoli mostrati esplicitamente
• Tutti i valori dai dati forniti, mai inventati

FOCUS ESCLUSIVO SULL'ANDAMENTO DEL CENTRALINO.
"""

def create_rulebased_analysis_prompt(data: Dict) -> str:
    """Create specialized prompt for RuleBased analysis focused on call center performance"""
    summary = data.get('summary', {})
    daily_breakdown = data.get('daily_breakdown', [])
    hourly_analysis = data.get('hourly_analysis', {})
    transfer_analysis = data.get('transfer_analysis', {})
    insights = data.get('insights', {})
    specific_details = data.get('specific_details', {})
    
    peak_hours = hourly_analysis.get('peak_hours', [])
    critical_hours = hourly_analysis.get('critical_hours', [])
    
    # Extract specific names, identifiers, dates
    full_names = specific_details.get('unique_full_names', [])  # Full names from <name> tag
    rulebased_names = specific_details.get('unique_rulebased_names', [])  # From grouping_name
    identifiers = specific_details.get('unique_object_identifiers', [])
    group_names = specific_details.get('unique_group_names', [])
    all_periods = specific_details.get('all_periods', [])
    
    # Build specific details section - prioritize full names
    details_section = ""
    if full_names:
        details_section += f"\n- Nomi completi RuleBased analizzati: {', '.join(full_names)}\n"
    elif rulebased_names:
        details_section += f"\n- Nomi RuleBased analizzati: {', '.join(rulebased_names)}\n"
    if identifiers:
        details_section += f"- Identificatori/numeri RuleBased: {', '.join(identifiers)}\n"
    if group_names:
        details_section += f"- Gruppi di appartenenza: {', '.join(group_names)}\n"
    if all_periods:
        details_section += f"- Date specifiche nel report: {', '.join(all_periods[:10])}{'...' if len(all_periods) > 10 else ''}\n"
    
    # Build entity names section - handle multiple RuleBased functions
    actual_rb_names = [n for n in full_names if n and n != 'Total'] if full_names else []
    if not actual_rb_names and rulebased_names:
        actual_rb_names = [n for n in rulebased_names if n and n != 'Total']
    
    entities_section = ""
    if len(actual_rb_names) == 1:
        entities_section = f"\n📞 FUNZIONE RULEBASED ANALIZZATA: {actual_rb_names[0]}\n"
    elif len(actual_rb_names) > 1:
        entities_section = f"\n📞 FUNZIONI RULEBASED ANALIZZATE ({len(actual_rb_names)}):\n"
        for idx, name in enumerate(actual_rb_names, 1):
            entities_section += f"   {idx}. {name}\n"
        entities_section += "\n⚠️ IMPORTANTE: Questo report contiene dati per MULTIPLE FUNZIONI RULEBASED. Devi differenziare le analisi per ogni funzione quando possibile.\n"
    
    return f"""
Analizza questo report RULEBASED per Setera Centralino e fornisci insights ULTRA-DETTAGLIATI in italiano FOCALIZZATI ESCLUSIVAMENTE SULL'ANDAMENTO DEL CENTRALINO.
{entities_section}

⚠️ CRITICO - RICONOSCIMENTO DATI FILTRATI/PARZIALI:
I report possono essere pre-filtrati e contenere solo un sottoinsieme di dati (es: solo una funzione RuleBased, solo un periodo specifico, solo determinati tipi di chiamate).
- Se un dato è 0 o mancante, VERIFICA se il report è filtrato prima di generare alert
- NON generare alert su dati mancanti se il report è chiaramente filtrato
- Analizza SOLO i dati presenti nel report, non quelli assenti per filtri
- Se il report contiene solo un sottoinsieme di funzioni RuleBased o tipi di chiamate, concentrati su quello e non segnalare come criticità l'assenza di altri dati
- Genera alert SOLO su anomalie nei dati effettivamente presenti, non su dati mancanti per filtri

IMPORTANTE: 
- Se ci sono MULTIPLE FUNZIONI RULEBASED nel report, DEVI differenziare le analisi per ogni funzione
- Crea tabelle separate o colonne per funzione quando i dati lo permettono
- Menti esplicitamente i nomi delle funzioni RuleBased nelle analisi

IMPORTANTE: Devi includere SEMPRE nei tuoi insights i dettagli specifici reali estratti dai dati XML:
{details_section}

Devi menzionare esplicitamente:
- I nomi completi specifici delle funzioni RuleBased analizzate (es. "Others/belal.darwish - Belal Darwish", non generici)
- I numeri/identificatori delle funzioni quando disponibili
- Le date specifiche (non "alcuni giorni" ma le date reali come "15 gennaio", "20 febbraio", ecc.)
- I gruppi di appartenenza quando disponibili
- Gli orari specifici (non "mattina" ma "09:00", "10:00", ecc.)

📊 DATI GENERALI CENTRALINO:
🗓️ Periodo: {data.get('period_range', 'N/A')}
📞 Chiamate gestite da rulebase: {summary.get('handled_by_rulebase', 0)}
✅ Chiamate connesse: {summary.get('connected', 0)}
❌ Chiamate non connesse: {summary.get('not_connected', 0)}
📈 Tasso di connessione: {summary.get('connection_rate', 0)}%
❌ Errori: {summary.get('failures', 0)}
🔄 Trasferimenti totali: {summary.get('total_transfers', 0)}

📈 BREAKDOWN GIORNALIERO:
{json.dumps(daily_breakdown, indent=2) if daily_breakdown else 'Nessun dato giornaliero'}

🕐 ANALISI ORARIA CENTRALINO:
Ore di picco: {json.dumps(peak_hours, indent=2) if peak_hours else 'Nessun picco'}
Ore critiche (connessione <70%): {json.dumps(critical_hours, indent=2) if critical_hours else 'Nessuna ora critica'}
Ore attive: {hourly_analysis.get('active_hours', 0)}

📲 ANALISI TRASFERIMENTI:
Destinazioni: {json.dumps(transfer_analysis.get('destinations', {}), indent=2)}
Destinazione più popolare: {transfer_analysis.get('most_popular_destination', 'N/A')}
Distribuzione: {json.dumps(transfer_analysis.get('transfer_distribution', {}), indent=2)}

FORNISCI UN'ANALISI ULTRA-PRECISA FOCALIZZATA SULL'ANDAMENTO DEL CENTRALINO:

🔍 1. PERFORMANCE CENTRALINO - METRICHE AVANZATE RULEBASED (calcolate dai dati reali)
   Crea una TABELLA con queste metriche RULEBASED calcolate:
   
   | Metrica RULEBASED | Valore | Target | Status | Calcolo |
   |-------------------|--------|--------|--------|---------|
   | Tasso connessione | {summary.get('connection_rate', 0)}% | >90% | [calcola] | connected / handled_by_rulebase |
   | Tasso non connessione | {calculate_percentage(summary.get('not_connected', 0), summary.get('handled_by_rulebase', 1))}% | <10% | [calcola] | not_connected / handled |
   | Tasso fallimenti | {calculate_percentage(summary.get('failures', 0), summary.get('handled_by_rulebase', 1))}% | <5% | [calcola] | failures / handled |
   | Tasso trasferimenti | {calculate_percentage(summary.get('total_transfers', 0), summary.get('handled_by_rulebase', 1)) if summary.get('handled_by_rulebase', 0) > 0 else 0}% | [analizza] | [calcola] | transfers / handled |
   | Efficienza routing | [calcola]% | >85% | [calcola] | (connected / handled) × (1 - failure_rate) |
   | Chiamate gestite | {summary.get('handled_by_rulebase', 0)} | [analizza] | [calcola] | total_handled_by_rulebase |
   
   • Analizza efficienza routing basato su regole con calcoli specifici
   • Valuta capacità centralino di instradare correttamente: calcola success rate
   • Identifica regole routing inefficienti: confronta tasso connessione per regola

📊 2. GESTIONE TRASFERIMENTI - ANALISI DETTAGLIATA
   Crea una TABELLA trasferimenti:
   
   | Destinazione | Quantità | % su Totali | % su Trasferimenti | Success Rate | Analisi | Azione |
   |--------------|----------|-------------|-------------------|--------------|---------|--------|
   [per ogni destinazione nei dati transfer_analysis, inserisci valori reali]
   
   • Analizza trasferimenti con dati precisi:
     - Destinazioni più utilizzate: top 5 con quantità dai dati
     - Distribuzione carico: calcola deviazione standard tra destinazioni
     - Efficienza trasferimenti: success rate per destinazione
   • Identifica pattern trasferimento:
     - Correlazione con orari: calcola per fascia oraria dai dati
     - Correlazione con volume: calcola coefficiente correlazione
   • Suggerisci ottimizzazioni routing con impatto quantificato

🎯 3. ANALISI TEMPORALE - TABELLE E SCHEMI
   Crea una TABELLA ORARIA RULEBASED:
   
   | Ora | Gestite | Connesse | Non Connesse | Fallimenti | Tasso Connessione | Tasso Fallimenti |
   |-----|---------|----------|--------------|------------|-------------------|------------------|
   [per ogni ora nei dati orari, inserisci i valori reali]
   
   Crea SCHEMA ASCII distribuzione oraria e pattern routing
   
   • Identifica fasce orarie critiche con dati precisi:
     - Quando routing fallisce più spesso: lista orari con failure_rate >5%
     - Pattern connessione nel tempo: trend analysis dai dati
     - Correlazioni volume vs successo routing: calcola coefficiente
   • Analizza capacità gestione nel tempo: variabilità e trend

💡 4. ANALISI FALLIMENTI E ERRORI - METRICHE AVANZATE
   Crea una TABELLA fallimenti:
   
   | Tipo | Quantità | % su Totali | Trend | Causa Probabile | Azione Correttiva | Impatto |
   |------|----------|-------------|-------|-----------------|-------------------|---------|
   | Fallimenti sistema | {summary.get('failures', 0)} | [calcola] | [analizza] | [analizza] | [suggerisci] | [quantifica] |
   | Non connesse | {summary.get('not_connected', 0)} | [calcola] | [analizza] | [analizza] | [suggerisci] | [quantifica] |
   
   • Analizza pattern fallimenti: correlazione con orari, giorni, volumi dai dati
   • Calcola costo fallimenti: (fallimenti × costo medio chiamata persa)
   • Identifica regole problematiche: confronta failure rate per regola

⚡ 5. RACCOMANDAZIONI OPERATIVE - PRIORITIZZATE CON DATI
   Crea una TABELLA priorità:
   
   | Priorità | Raccomandazione | Impatto Atteso | Dati Supporto | Timeline | ROI |
   |----------|----------------|----------------|---------------|----------|-----|
   | 🔴 Alta | [specifica] | [quantifica] | [riferisci dati] | [specifica] | [calcola] |
   | 🟡 Media | [specifica] | [quantifica] | [riferisci dati] | [specifica] | [calcola] |
   | 🟢 Bassa | [specifica] | [quantifica] | [riferisci dati] | [specifica] | [calcola] |
   
   Ogni raccomandazione basata su dati reali

📈 6. DASHBOARD RULEBASED - KPI CON VALORI REALI
   Crea una TABELLA KPI completa:
   
   | KPI | Valore Attuale | Target | Gap | Trend | Alert Soglia |
   |-----|----------------|--------|-----|-------|--------------|
   | Tasso connessione | {summary.get('connection_rate', 0)}% | >90% | [calcola] | [analizza] | <85% |
   | Tasso fallimenti | [calcola]% | <5% | [calcola] | [analizza] | >8% |
   | Efficienza routing | [calcola]% | >85% | [calcola] | [analizza] | <75% |
   | Tasso trasferimenti | [calcola]% | [analizza] | [calcola] | [analizza] | [soglia] |
   | Chiamate gestite | {summary.get('handled_by_rulebase', 0)} | [analizza] | [calcola] | [analizza] | [soglia] |

🎨 FORMATTAZIONE OBBLIGATORIA:
• MINIMO 4 TABELLE con dati reali (metriche, trasferimenti, oraria, fallimenti)
• MINIMO 1 SCHEMA/GRAFICO ASCII (distribuzione oraria, pattern routing)
• Sistema colori: 🟢 (ok), 🟡 (attenzione), 🔴 (critico)
• Tutti i calcoli mostrati esplicitamente
• Tutti i valori dai dati forniti, mai inventati

FOCUS ESCLUSIVO SULL'ANDAMENTO DEL CENTRALINO.
"""

def create_generic_analysis_prompt(data: Dict) -> str:
    """Create generic prompt for other report types"""
    return f"""
Analizza questo report telefonico per Setera Centralino e fornisci insights in italiano:

DATI REPORT:
{json.dumps(data, indent=2, cls=DecimalEncoder)}

Fornisci un'analisi professionale che includa:
1. Sintesi dei dati principali
2. Trend e pattern identificati
3. Aree di miglioramento
4. Raccomandazioni operative

Scrivi in italiano professionale e concentrati su insights pratici.
"""

def generate_fallback_insights(data: Dict) -> str:
    """Generate basic insights if Claude fails"""
    report_type = data.get('report_type', 'unknown')
    summary = data.get('summary', {})
    
    if report_type == 'acd':
        answer_rate = summary.get('answer_rate', 0)
        service_level = summary.get('service_level_20s', 0)
        total_calls = summary.get('total_incoming_calls', 0)
        answered = summary.get('answered_calls', 0)
        unanswered = summary.get('unanswered_calls', 0)
        avg_speed = summary.get('avg_speed_of_answer', 0)
        
        answer_status = "🟢" if answer_rate >= 85 else "🟡" if answer_rate >= 70 else "🔴"
        sl_status = "🟢" if service_level >= 80 else "🟡" if service_level >= 70 else "🔴"
        speed_status = "🟢" if avg_speed <= 20 else "🟡" if avg_speed <= 30 else "🔴"
        
        return f"""
        📊 <strong>MAYA ANALYTICS - REPORT ACD (CENTRALINO)</strong>
        
        🎯 <strong>PERFORMANCE CENTRALINO</strong>
        {answer_status} Tasso di risposta: <strong>{answer_rate}%</strong>
        {sl_status} Service Level (20s): <strong>{service_level}%</strong>
        {speed_status} Velocità media risposta: <strong>{avg_speed}s</strong>
        
        📈 <strong>METRICHE CENTRALINO</strong>
        📞 Chiamate totali: <strong>{total_calls}</strong>
        ✅ Chiamate risposte: <strong>{answered}</strong>
        ❌ Chiamate non risposte: <strong>{unanswered}</strong>
        🔄 Reindirizzate: <strong>{summary.get('total_redirected', 0)}</strong>
        📞 Callback richiesti: <strong>{summary.get('callbacks_requested', 0)}</strong>
        
        💡 <strong>INSIGHTS CENTRALINO</strong>
        • {("🟢 Centralino operativo efficiente" if answer_rate >= 85 and service_level >= 80 else "⚠️ Centralino necessita ottimizzazione" if answer_rate >= 70 else "🚨 Attenzione: performance centralino critiche")}
        • {("🟢 Service Level ottimale" if service_level >= 80 else "⚠️ Service Level da migliorare" if service_level >= 70 else "🚨 Service Level critico")}
        • 📊 Analisi completa centralino in preparazione...
        
        🔧 <strong>RACCOMANDAZIONI CENTRALINO</strong>
        💎 Monitoraggio continuo performance centralino
        📈 Analisi trend code e distribuzione
        ⚡ Ottimizzazione staffing e gestione code
        
        <em>⚠️ Report dettagliato con Claude temporaneamente non disponibile</em>
        """
    
    elif report_type == 'user':
        answer_rate = summary.get('answer_rate', 0)
        total_incoming = summary.get('incoming_total', 0)
        total_outgoing = summary.get('outgoing_total', 0)
        answered = summary.get('incoming_answered', 0)
        
        answer_status = "🟢" if answer_rate >= 85 else "🟡" if answer_rate >= 70 else "🔴"
        
        return f"""
        📊 <strong>MAYA ANALYTICS - REPORT USER (CENTRALINO)</strong>
        
        🎯 <strong>PERFORMANCE CENTRALINO</strong>
        {answer_status} Tasso di risposta: <strong>{answer_rate}%</strong>
        
        📈 <strong>METRICHE CENTRALINO</strong>
        📞 Chiamate in arrivo: <strong>{total_incoming}</strong>
        📤 Chiamate in uscita: <strong>{total_outgoing}</strong>
        ✅ Chiamate risposte: <strong>{answered}</strong>
        ⏱️ Durata totale: <strong>{summary.get('total_duration', 'N/A')}</strong>
        
        💡 <strong>INSIGHTS CENTRALINO</strong>
        • {("🟢 Utilizzo centralino efficiente" if answer_rate >= 85 else "⚠️ Centralino necessita ottimizzazione" if answer_rate >= 70 else "🚨 Performance centralino critiche")}
        • 📊 Analisi completa centralino in preparazione...
        
        <em>⚠️ Report dettagliato con Claude temporaneamente non disponibile</em>
        """
    
    elif report_type == 'huntgroup':
        answer_rate = summary.get('answer_rate', 0)
        overflow_rate = summary.get('overflow_rate', 0)
        total_calls = summary.get('incoming_total', 0)
        answered = summary.get('answered_by_members', 0)
        
        answer_status = "🟢" if answer_rate >= 85 else "🟡" if answer_rate >= 70 else "🔴"
        overflow_status = "🟢" if overflow_rate <= 10 else "🟡" if overflow_rate <= 15 else "🔴"
        
        return f"""
        📊 <strong>MAYA ANALYTICS - REPORT HUNTGROUP (CENTRALINO)</strong>
        
        🎯 <strong>PERFORMANCE CENTRALINO</strong>
        {answer_status} Tasso di risposta: <strong>{answer_rate}%</strong>
        {overflow_status} Tasso di overflow: <strong>{overflow_rate}%</strong>
        
        📈 <strong>METRICHE CENTRALINO</strong>
        📞 Chiamate totali: <strong>{total_calls}</strong>
        ✅ Risposte da membri: <strong>{answered}</strong>
        🔄 Inviate a overflow: <strong>{summary.get('sent_to_overflow', 0)}</strong>
        
        💡 <strong>INSIGHTS CENTRALINO</strong>
        • {("🟢 Distribuzione centralino efficiente" if answer_rate >= 85 and overflow_rate <= 10 else "⚠️ Centralino necessita ottimizzazione" if answer_rate >= 70 else "🚨 Performance centralino critiche")}
        • 📊 Analisi completa centralino in preparazione...
        
        <em>⚠️ Report dettagliato con Claude temporaneamente non disponibile</em>
        """
    
    elif report_type == 'rulebased':
        connection_rate = summary.get('connection_rate', 0)
        total_handled = summary.get('handled_by_rulebase', 0)
        connected = summary.get('connected', 0)
        
        connection_status = "🟢" if connection_rate >= 90 else "🟡" if connection_rate >= 80 else "🔴"
        
        return f"""
        📊 <strong>MAYA ANALYTICS - REPORT RULEBASED (CENTRALINO)</strong>
        
        🎯 <strong>PERFORMANCE CENTRALINO</strong>
        {connection_status} Tasso di connessione: <strong>{connection_rate}%</strong>
        
        📈 <strong>METRICHE CENTRALINO</strong>
        📞 Chiamate gestite: <strong>{total_handled}</strong>
        ✅ Chiamate connesse: <strong>{connected}</strong>
        🔄 Trasferimenti: <strong>{summary.get('total_transfers', 0)}</strong>
        ❌ Errori: <strong>{summary.get('failures', 0)}</strong>
        
        💡 <strong>INSIGHTS CENTRALINO</strong>
        • {("🟢 Routing centralino efficiente" if connection_rate >= 90 else "⚠️ Routing centralino necessita ottimizzazione" if connection_rate >= 80 else "🚨 Performance routing centralino critiche")}
        • 📊 Analisi completa centralino in preparazione...
        
        <em>⚠️ Report dettagliato con Claude temporaneamente non disponibile</em>
        """
    
    elif report_type == 'ivr':
        summary = data.get('summary', {})
        
        # Enhanced IVR fallback with symbols and formatting
        connection_rate = summary.get('connection_rate', 0)
        total_calls = summary.get('total_calls', 0)
        connected_calls = summary.get('connected_calls', 0)
        abandoned_calls = summary.get('abandoned_calls', 0)
        avg_duration = summary.get('avg_call_duration', 0)
        
        # Status indicators based on performance
        connection_status = "🟢" if connection_rate >= 85 else "🟡" if connection_rate >= 70 else "🔴"
        duration_status = "🟢" if avg_duration <= 20 else "🟡" if avg_duration <= 30 else "🔴"
        
        return f"""
        📊 <strong>MAYA ANALYTICS - REPORT IVR</strong>
        
        🎯 <strong>PERFORMANCE OVERVIEW</strong>
        {connection_status} Tasso di connessione: <strong>{connection_rate}%</strong>
        ⏱️ Durata media IVR: <strong>{avg_duration}s</strong> {duration_status}
        
        📈 <strong>METRICHE DETTAGLIATE</strong>
        📞 Chiamate totali: <strong>{total_calls}</strong>
        ✅ Chiamate connesse: <strong>{connected_calls}</strong>
        ❌ Chiamate abbandonate: <strong>{abandoned_calls}</strong>
        
        💡 <strong>INSIGHTS AUTOMATICI</strong>
        • {("🟢 Sistema operativo efficiente" if connection_rate >= 85 else "⚠️ Sistema necessita ottimizzazione" if connection_rate >= 70 else "🚨 Attenzione: performance critiche")}
        • {("🟢 Durata IVR ottimale" if avg_duration <= 20 else "⚠️ Durata IVR da ridurre" if avg_duration <= 30 else "🚨 Durata IVR eccessiva")}
        • 📊 Analisi completa in preparazione...
        
        🔧 <strong>RACCOMANDAZIONI RAPIDE</strong>
        💎 Monitoraggio continuo performance
        📈 Analisi trend settimanali  
        ⚡ Ottimizzazione flussi IVR
        
        <em>⚠️ Report dettagliato con Claude temporaneamente non disponibile</em>
        """
    else:
        return f"""
        📊 <strong>MAYA ANALYTICS - REPORT {report_type.upper()}</strong>
        
        ✅ Report elaborato con successo
        📋 Tipologia: <strong>{report_type}</strong>
        📊 Dati raccolti e processati
        🤖 Analisi AI in corso...
        
        💡 <strong>SISTEMA OPERATIVO</strong>
        • ✅ Connessione endpoint attiva
        • 📊 Dati XML processati
        • 🎯 Metriche estratte
        
        <em>⚠️ Analisi dettagliata temporaneamente non disponibile</em>
        """

# ========================================
# CHART GENERATION (QuickSight-style)
# ========================================

# Setera brand colors (professional palette)
SETERA_COLORS = {
    'primary': '#1E3A8A',      # Deep blue
    'secondary': '#3B82F6',    # Bright blue
    'accent': '#10B981',       # Green
    'warning': '#F59E0B',      # Orange
    'danger': '#EF4444',       # Red
    'success': '#10B981',      # Green
    'info': '#3B82F6',         # Blue
    'light': '#F3F4F6',        # Light gray
    'dark': '#1F2937',         # Dark gray
    'background': '#FFFFFF',    # White
    'text': '#111827',          # Dark text
    'text_light': '#6B7280'     # Light text
}

def generate_chart_base64(fig) -> str:
    """Convert matplotlib figure to base64 string for email embedding"""
    try:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_base64
    except Exception as e:
        logger.error(f"❌ Error generating chart base64: {str(e)}")
        return ""

def generate_line_chart(data: Dict, title: str, xlabel: str = "", ylabel: str = "") -> str:
    """Generate line chart like QuickSight"""
    try:
        fig, ax = plt.subplots(figsize=(10, 5), facecolor='white')
        
        x_data = data.get('x', [])
        y_data = data.get('y', [])
        
        if not x_data or not y_data:
            return ""
        
        ax.plot(x_data, y_data, color=SETERA_COLORS['primary'], linewidth=2.5, marker='o', 
               markersize=6, markerfacecolor=SETERA_COLORS['secondary'], 
               markeredgecolor=SETERA_COLORS['primary'], markeredgewidth=1.5)
        
        ax.set_title(title, fontsize=14, fontweight='bold', color=SETERA_COLORS['text'], pad=15)
        if xlabel:
            ax.set_xlabel(xlabel, fontsize=11, color=SETERA_COLORS['text_light'])
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=11, color=SETERA_COLORS['text_light'])
        
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(SETERA_COLORS['light'])
        ax.spines['bottom'].set_color(SETERA_COLORS['light'])
        ax.tick_params(colors=SETERA_COLORS['text_light'], labelsize=10)
        
        plt.tight_layout()
        return generate_chart_base64(fig)
    except Exception as e:
        logger.error(f"❌ Error generating line chart: {str(e)}")
        return ""

def generate_bar_chart(data: Dict, title: str, xlabel: str = "", ylabel: str = "", horizontal: bool = False) -> str:
    """Generate bar chart like QuickSight"""
    try:
        fig, ax = plt.subplots(figsize=(10, 6), facecolor='white')
        
        x_data = data.get('x', [])
        y_data = data.get('y', [])
        colors = data.get('colors', [SETERA_COLORS['primary']] * len(y_data))
        
        if not x_data or not y_data:
            return ""
        
        if horizontal:
            bars = ax.barh(x_data, y_data, color=colors, edgecolor='white', linewidth=1.5, height=0.6)
        else:
            bars = ax.bar(x_data, y_data, color=colors, edgecolor='white', linewidth=1.5, width=0.6)
        
        # Add value labels on bars
        for i, (bar, val) in enumerate(zip(bars, y_data)):
            height = bar.get_height() if not horizontal else bar.get_width()
            ax.text(bar.get_x() + bar.get_width()/2. if not horizontal else height + max(y_data)*0.01,
                   height + max(y_data)*0.01 if not horizontal else bar.get_y() + bar.get_height()/2.,
                   f'{val}', ha='center' if not horizontal else 'left', va='bottom' if not horizontal else 'center',
                   fontsize=9, fontweight='bold', color=SETERA_COLORS['text'])
        
        ax.set_title(title, fontsize=14, fontweight='bold', color=SETERA_COLORS['text'], pad=15)
        if xlabel:
            ax.set_xlabel(xlabel, fontsize=11, color=SETERA_COLORS['text_light'])
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=11, color=SETERA_COLORS['text_light'])
        
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, axis='y' if not horizontal else 'x')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(SETERA_COLORS['light'])
        ax.spines['bottom'].set_color(SETERA_COLORS['light'])
        ax.tick_params(colors=SETERA_COLORS['text_light'], labelsize=10)
        
        plt.tight_layout()
        return generate_chart_base64(fig)
    except Exception as e:
        logger.error(f"❌ Error generating bar chart: {str(e)}")
        return ""

def generate_pie_chart(data: Dict, title: str) -> str:
    """Generate pie chart like QuickSight"""
    try:
        fig, ax = plt.subplots(figsize=(8, 8), facecolor='white')
        
        labels = data.get('labels', [])
        values = data.get('values', [])
        colors_palette = [SETERA_COLORS['primary'], SETERA_COLORS['secondary'], SETERA_COLORS['accent'],
                         SETERA_COLORS['warning'], SETERA_COLORS['danger'], SETERA_COLORS['info']]
        
        if not labels or not values:
            return ""
        
        colors = [colors_palette[i % len(colors_palette)] for i in range(len(labels))]
        
        wedges, texts, autotexts = ax.pie(values, labels=labels, colors=colors, autopct='%1.1f%%',
                                          startangle=90, textprops={'fontsize': 10, 'fontweight': 'bold'})
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        ax.set_title(title, fontsize=14, fontweight='bold', color=SETERA_COLORS['text'], pad=20)
        
        plt.tight_layout()
        return generate_chart_base64(fig)
    except Exception as e:
        logger.error(f"❌ Error generating pie chart: {str(e)}")
        return ""

def generate_gauge_chart(value: float, max_value: float, title: str, threshold_good: float = 0.7, threshold_warning: float = 0.5) -> str:
    """Generate gauge/KPI chart like QuickSight"""
    try:
        fig, ax = plt.subplots(figsize=(6, 4), facecolor='white')
        
        percentage = value / max_value if max_value > 0 else 0
        
        # Determine color based on threshold
        if percentage >= threshold_good:
            color = SETERA_COLORS['success']
        elif percentage >= threshold_warning:
            color = SETERA_COLORS['warning']
        else:
            color = SETERA_COLORS['danger']
        
        # Draw gauge arc
        theta = np.linspace(0, np.pi, 100)
        r = 1
        
        # Background arc
        ax.plot(theta, [r]*100, color=SETERA_COLORS['light'], linewidth=20, solid_capstyle='round')
        
        # Value arc
        value_theta = np.linspace(0, np.pi * percentage, int(100 * percentage))
        ax.plot(value_theta, [r]*len(value_theta), color=color, linewidth=20, solid_capstyle='round')
        
        # Value text
        ax.text(0, 0.3, f'{value:.1f}', ha='center', va='center', fontsize=24, fontweight='bold', color=SETERA_COLORS['text'])
        ax.text(0, -0.2, title, ha='center', va='center', fontsize=11, color=SETERA_COLORS['text_light'])
        
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-0.5, 1.2)
        ax.axis('off')
        
        plt.tight_layout()
        return generate_chart_base64(fig)
    except Exception as e:
        logger.error(f"❌ Error generating gauge chart: {str(e)}")
        return ""

def extract_chart_data_from_parsed(parsed_data: Dict) -> Dict:
    """Extract structured data from parsed_data for chart generation - supports all report types"""
    charts_data = {
        'hourly_trend': None,
        'daily_breakdown': None,
        'kpi_gauges': [],
        'distribution_charts': [],
        'pie_charts': []
    }
    
    try:
        report_type = parsed_data.get('report_type', '')
        summary = parsed_data.get('summary', {})
        
        # Extract hourly data for trend chart (all report types)
        hourly_analysis = parsed_data.get('hourly_analysis', {})
        all_hourly_data = hourly_analysis.get('all_hourly_data', [])
        
        if all_hourly_data:
            hours = []
            values = []
            for hour_data in all_hourly_data[:24]:  # Limit to 24 hours
                period = hour_data.get('period', '')
                if period and period != 'Total':
                    # Extract hour from period (e.g., "14:00 - 14:30" -> "14:00")
                    hour_str = period.split(' - ')[0] if ' - ' in period else period
                    hours.append(hour_str)
                    
                    # Use appropriate metric based on report type
                    if report_type == 'ivr':
                        values.append(hour_data.get('total_handled', 0) or 0)
                    elif report_type == 'rulebased':
                        values.append(hour_data.get('handled_by_rulebase', 0) or 0)
                    elif report_type == 'huntgroup':
                        values.append(hour_data.get('incoming_total', 0) or 0)
                    elif report_type == 'acd':
                        values.append(hour_data.get('incoming_total', 0) or 0)
                    else:  # user
                        total = (hour_data.get('incoming_total', 0) or 0) + (hour_data.get('outgoing_total', 0) or 0)
                        values.append(total)
            
            if hours and values and any(v > 0 for v in values):
                charts_data['hourly_trend'] = {
                    'x': hours,
                    'y': values,
                    'title': 'Trend Chiamate per Ora',
                    'xlabel': 'Ora',
                    'ylabel': 'Numero Chiamate'
                }
        
        # Extract daily breakdown for bar chart (all report types)
        daily_breakdown = parsed_data.get('daily_breakdown', [])
        if daily_breakdown:
            days = []
            incoming = []
            outgoing = []
            answered = []
            unanswered = []
            
            for day in daily_breakdown[:7]:  # Limit to 7 days
                period = day.get('period', '')
                if period and period != 'Total':
                    days.append(period)
                    
                    # Extract metrics based on report type
                    if report_type in ['user', 'acd', 'huntgroup']:
                        incoming.append(day.get('incoming_total', 0) or day.get('incoming_handled', 0) or 0)
                        outgoing.append(day.get('outgoing_total', 0) or 0)
                        answered.append(day.get('incoming_answered', 0) or day.get('answered_by_members', 0) or 0)
                        unanswered.append(day.get('incoming_unanswered', 0) or day.get('unanswered_by_members', 0) or 0)
                    elif report_type in ['ivr', 'rulebased']:
                        incoming.append(day.get('total_handled', 0) or day.get('handled_by_rulebase', 0) or 0)
                        outgoing.append(0)  # No outgoing for IVR/RuleBased
                        answered.append(day.get('connected', 0) or 0)
                        unanswered.append(day.get('not_connected', 0) or 0)
            
            if days:
                # Use incoming/outgoing if available, otherwise use answered/unanswered
                if any(incoming) or any(outgoing):
                    charts_data['daily_breakdown'] = {
                        'days': days,
                        'incoming': incoming,
                        'outgoing': outgoing,
                        'title': 'Breakdown Giornaliero - Chiamate In/Out'
                    }
                elif any(answered) or any(unanswered):
                    charts_data['daily_breakdown'] = {
                        'days': days,
                        'incoming': answered,
                        'outgoing': unanswered,
                        'title': 'Breakdown Giornaliero - Risposte/Non Risposte'
                    }
        
        # Extract KPI data for gauges (all report types)
        if summary:
            # Answer rate / Connection rate gauge
            answer_rate = summary.get('answer_rate', 0) or summary.get('connection_rate', 0)
            if answer_rate > 0:
                charts_data['kpi_gauges'].append({
                    'value': answer_rate,
                    'max': 100,
                    'title': 'Tasso Risposta' if report_type != 'ivr' else 'Tasso Connessione',
                    'threshold_good': 0.85,
                    'threshold_warning': 0.70
                })
            
            # Service level gauge (ACD, HuntGroup)
            service_level = summary.get('service_level_20s', 0) or summary.get('service_level', 0)
            if service_level > 0:
                charts_data['kpi_gauges'].append({
                    'value': service_level,
                    'max': 100,
                    'title': 'Service Level',
                    'threshold_good': 0.80,
                    'threshold_warning': 0.60
                })
            
            # Speed of answer gauge
            speed_of_answer = summary.get('avg_speed_of_answer', 0) or summary.get('incoming_avg_speed_of_answer', 0)
            if speed_of_answer > 0:
                charts_data['kpi_gauges'].append({
                    'value': speed_of_answer,
                    'max': 60,  # 60 seconds max
                    'title': 'Velocità Risposta (s)',
                    'threshold_good': 0.33,  # <20s is good (20/60)
                    'threshold_warning': 0.50  # <30s is warning (30/60)
                })
            
            # Abandonment rate gauge (inverted - lower is better)
            abandonment_rate = summary.get('abandonment_rate', 0)
            if abandonment_rate > 0:
                charts_data['kpi_gauges'].append({
                    'value': abandonment_rate,
                    'max': 100,
                    'title': 'Tasso Abbandono',
                    'threshold_good': 0.15,  # <15% is good
                    'threshold_warning': 0.25  # <25% is warning
                })
        
        # Extract distribution data for pie charts
        if summary:
            # Call distribution (answered vs unanswered)
            total_answered = summary.get('incoming_answered', 0) or summary.get('connected', 0) or 0
            total_unanswered = summary.get('incoming_unanswered', 0) or summary.get('not_connected', 0) or 0
            total_redirected = summary.get('incoming_redirected', 0) or 0
            
            if total_answered + total_unanswered + total_redirected > 0:
                pie_data = {
                    'labels': [],
                    'values': []
                }
                if total_answered > 0:
                    pie_data['labels'].append('Risposte')
                    pie_data['values'].append(total_answered)
                if total_unanswered > 0:
                    pie_data['labels'].append('Non Risposte')
                    pie_data['values'].append(total_unanswered)
                if total_redirected > 0:
                    pie_data['labels'].append('Reindirizzate')
                    pie_data['values'].append(total_redirected)
                
                if len(pie_data['labels']) > 1:
                    charts_data['pie_charts'].append({
                        'data': pie_data,
                        'title': 'Distribuzione Chiamate'
                    })
        
    except Exception as e:
        logger.error(f"❌ Error extracting chart data: {str(e)}")
    
    return charts_data

# ========================================
# EMAIL FORMATTING
# ========================================

def format_email_content(user_data: Dict, insights: str, parsed_data: Dict = None) -> str:
    """Format the final email content with insights, charts, and QuickSight-style layout"""
    try:
        # Extract only the first name from the full name
        full_name = user_data.get('name', 'Utente')
        user_name = full_name.split()[0] if full_name else 'Utente'
        timestamp = datetime.utcnow().strftime('%d/%m/%Y %H:%M')
        
        # Generate charts if parsed_data is available
        charts_html = ""
        kpi_cards_html = ""
        if parsed_data:
            try:
                charts_data = extract_chart_data_from_parsed(parsed_data)
                summary = parsed_data.get('summary', {})
                
                # Generate KPI cards
                kpi_cards = []
                if summary.get('answer_rate', 0) > 0:
                    kpi_cards.append({
                        'title': 'Tasso Risposta',
                        'value': f"{summary.get('answer_rate', 0):.1f}%",
                        'status': 'good' if summary.get('answer_rate', 0) >= 85 else 'warning' if summary.get('answer_rate', 0) >= 70 else 'danger'
                    })
                if summary.get('incoming_total', 0) > 0:
                    kpi_cards.append({
                        'title': 'Chiamate Totali',
                        'value': f"{summary.get('incoming_total', 0):,}",
                        'status': 'info'
                    })
                if summary.get('service_level_20s', 0) > 0 or summary.get('service_level', 0) > 0:
                    sl = summary.get('service_level_20s', 0) or summary.get('service_level', 0)
                    kpi_cards.append({
                        'title': 'Service Level',
                        'value': f"{sl:.1f}%",
                        'status': 'good' if sl >= 80 else 'warning' if sl >= 60 else 'danger'
                    })
                if summary.get('incoming_avg_speed_of_answer', 0) > 0:
                    kpi_cards.append({
                        'title': 'Velocità Risposta',
                        'value': f"{summary.get('incoming_avg_speed_of_answer', 0):.1f}s",
                        'status': 'good' if summary.get('incoming_avg_speed_of_answer', 0) <= 20 else 'warning'
                    })
                
                # Build KPI cards HTML
                if kpi_cards:
                    kpi_cards_html = '<div class="kpi-grid">'
                    for kpi in kpi_cards:
                        status_class = kpi['status']
                        kpi_cards_html += f'''
                        <div class="kpi-card {status_class}">
                            <div class="kpi-title">{kpi['title']}</div>
                            <div class="kpi-value">{kpi['value']}</div>
                        </div>
                        '''
                    kpi_cards_html += '</div>'
                
                # Generate charts - organize in sections
                chart_cards = []
                gauge_cards = []
                
                # Generate hourly trend line chart
                if charts_data.get('hourly_trend'):
                    trend_data = charts_data['hourly_trend']
                    chart_img = generate_line_chart(
                        {'x': trend_data['x'], 'y': trend_data['y']},
                        trend_data['title'],
                        trend_data.get('xlabel', ''),
                        trend_data.get('ylabel', '')
                    )
                    if chart_img:
                        chart_cards.append({
                            'title': trend_data['title'],
                            'img': chart_img
                        })
                
                # Generate daily breakdown bar chart
                if charts_data.get('daily_breakdown'):
                    daily_data = charts_data['daily_breakdown']
                    # Create grouped bar chart
                    x = np.arange(len(daily_data['days']))
                    width = 0.35
                    fig, ax = plt.subplots(figsize=(10, 6), facecolor='white')
                    bars1 = ax.bar(x - width/2, daily_data['incoming'], width, label='In Arrivo', 
                                  color=SETERA_COLORS['primary'], edgecolor='white', linewidth=1.5)
                    bars2 = ax.bar(x + width/2, daily_data['outgoing'], width, label='In Uscita', 
                                  color=SETERA_COLORS['secondary'], edgecolor='white', linewidth=1.5)
                    ax.set_xlabel('Giorno', fontsize=11, color=SETERA_COLORS['text_light'])
                    ax.set_ylabel('Numero Chiamate', fontsize=11, color=SETERA_COLORS['text_light'])
                    ax.set_title(daily_data['title'], fontsize=14, fontweight='bold', color=SETERA_COLORS['text'], pad=15)
                    ax.set_xticks(x)
                    ax.set_xticklabels(daily_data['days'], rotation=45, ha='right')
                    ax.legend(loc='upper left')
                    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, axis='y')
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    plt.tight_layout()
                    chart_img = generate_chart_base64(fig)
                    if chart_img:
                        chart_cards.append({
                            'title': daily_data['title'],
                            'img': chart_img
                        })
                
                # Generate KPI gauges
                for gauge_data in charts_data.get('kpi_gauges', [])[:4]:  # Limit to 4 gauges
                    gauge_img = generate_gauge_chart(
                        gauge_data['value'],
                        gauge_data['max'],
                        gauge_data['title'],
                        gauge_data.get('threshold_good', 0.7),
                        gauge_data.get('threshold_warning', 0.5)
                    )
                    if gauge_img:
                        gauge_cards.append({
                            'title': gauge_data['title'],
                            'img': gauge_img
                        })
                
                # Build charts HTML with proper organization
                if chart_cards:
                    charts_html += '<div class="chart-section"><h2 style="font-size: 20px; font-weight: 600; color: ' + SETERA_COLORS['text'] + '; margin: 30px 0 20px 0;">📈 Visualizzazioni Dati</h2><div class="chart-grid">'
                    for card in chart_cards:
                        charts_html += f'''
                        <div class="chart-card">
                            <h3 class="chart-title">{card['title']}</h3>
                            <img src="data:image/png;base64,{card['img']}" alt="{card['title']}" class="chart-image" />
                        </div>
                        '''
                    charts_html += '</div></div>'
                
                # Generate pie charts
                for pie_data in charts_data.get('pie_charts', []):
                    pie_img = generate_pie_chart(pie_data['data'], pie_data['title'])
                    if pie_img:
                        chart_cards.append({
                            'title': pie_data['title'],
                            'img': pie_img
                        })
                
                if gauge_cards:
                    charts_html += '<div class="chart-section"><h2 style="font-size: 20px; font-weight: 600; color: ' + SETERA_COLORS['text'] + '; margin: 30px 0 20px 0;">🎯 Indicatori KPI</h2><div class="gauge-grid">'
                    for card in gauge_cards:
                        charts_html += f'''
                        <div class="gauge-card">
                            <img src="data:image/png;base64,{card['img']}" alt="{card['title']}" class="gauge-image" />
                        </div>
                        '''
                    charts_html += '</div></div>'
            except Exception as e:
                logger.error(f"❌ Error generating charts: {str(e)}")
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="it">
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Maya Analytics Report - Setera</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    margin: 0; 
                    padding: 0;
                    background-color: {SETERA_COLORS['light']};
                    color: {SETERA_COLORS['text']};
                    line-height: 1.6;
                }}
                .email-wrapper {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: {SETERA_COLORS['background']};
                }}
                .header {{
                    background: linear-gradient(135deg, {SETERA_COLORS['primary']} 0%, {SETERA_COLORS['secondary']} 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 32px;
                    font-weight: 600;
                    letter-spacing: -0.5px;
                }}
                .header p {{
                    margin: 8px 0 0 0;
                    opacity: 0.95;
                    font-size: 16px;
                }}
                .content {{
                    padding: 30px;
                }}
                .timestamp {{
                    background: {SETERA_COLORS['light']};
                    padding: 12px 16px;
                    border-radius: 8px;
                    font-size: 13px;
                    color: {SETERA_COLORS['text_light']};
                    margin-bottom: 25px;
                    display: inline-block;
                }}
                .kpi-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin: 30px 0;
                }}
                .kpi-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                    border-left: 4px solid;
                    transition: transform 0.2s, box-shadow 0.2s;
                }}
                .kpi-card.good {{ border-left-color: {SETERA_COLORS['success']}; }}
                .kpi-card.warning {{ border-left-color: {SETERA_COLORS['warning']}; }}
                .kpi-card.danger {{ border-left-color: {SETERA_COLORS['danger']}; }}
                .kpi-card.info {{ border-left-color: {SETERA_COLORS['info']}; }}
                .kpi-title {{
                    font-size: 13px;
                    font-weight: 500;
                    color: {SETERA_COLORS['text_light']};
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 8px;
                }}
                .kpi-value {{
                    font-size: 32px;
                    font-weight: 700;
                    color: {SETERA_COLORS['text']};
                    line-height: 1.2;
                }}
                .chart-section {{
                    margin: 40px 0;
                }}
                .chart-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                    gap: 25px;
                    margin-top: 25px;
                }}
                .chart-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                }}
                .chart-title {{
                    font-size: 16px;
                    font-weight: 600;
                    color: {SETERA_COLORS['text']};
                    margin: 0 0 20px 0;
                }}
                .chart-image {{
                    width: 100%;
                    height: auto;
                    border-radius: 8px;
                }}
                .gauge-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 25px;
                    margin-top: 25px;
                }}
                .gauge-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                    text-align: center;
                }}
                .gauge-image {{
                    width: 100%;
                    max-width: 300px;
                    height: auto;
                }}
                .insights-section {{
                    background: white;
                    border-radius: 12px;
                    padding: 30px;
                    margin: 30px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                }}
                .insights-section h2 {{
                    font-size: 20px;
                    font-weight: 600;
                    color: {SETERA_COLORS['text']};
                    margin: 0 0 20px 0;
                    padding-bottom: 15px;
                    border-bottom: 2px solid {SETERA_COLORS['light']};
                }}
                .insights-content {{
                    color: {SETERA_COLORS['text']};
                    font-size: 15px;
                }}
                .insights-content p {{
                    margin: 15px 0;
                }}
                .insights-content ul, .insights-content ol {{
                    margin: 15px 0;
                    padding-left: 25px;
                }}
                .insights-content li {{
                    margin: 8px 0;
                }}
                .table-container {{
                    overflow-x: auto;
                    margin: 20px 0;
                }}
                .data-table {{
                    width: 100%;
                    border-collapse: collapse;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}
                .data-table th {{
                    background: {SETERA_COLORS['primary']};
                    color: white;
                    padding: 12px 16px;
                    text-align: left;
                    font-weight: 600;
                    font-size: 13px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .data-table td {{
                    padding: 12px 16px;
                    border-bottom: 1px solid {SETERA_COLORS['light']};
                    font-size: 14px;
                }}
                .data-table tr:hover {{
                    background: {SETERA_COLORS['light']};
                }}
                .data-table tr:last-child td {{
                    border-bottom: none;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                .status-good {{ background: {SETERA_COLORS['success']}; color: white; }}
                .status-warning {{ background: {SETERA_COLORS['warning']}; color: white; }}
                .status-danger {{ background: {SETERA_COLORS['danger']}; color: white; }}
                .footer {{
                    background: {SETERA_COLORS['dark']};
                    color: white;
                    padding: 25px 30px;
                    text-align: center;
                    font-size: 13px;
                    line-height: 1.8;
                }}
                .footer a {{
                    color: {SETERA_COLORS['secondary']};
                    text-decoration: none;
                }}
                @media only screen and (max-width: 600px) {{
                    .content {{ padding: 20px; }}
                    .kpi-grid {{ grid-template-columns: 1fr; }}
                    .chart-grid {{ grid-template-columns: 1fr; }}
                    .gauge-grid {{ grid-template-columns: 1fr; }}
                }}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="header">
                    <h1>🤖 Maya Analytics</h1>
                    <p>Report Automatico per Setera Centralino</p>
                </div>
                
                <div class="content">
                    <div class="timestamp">
                        📅 Generato il: {timestamp} UTC
                    </div>
                    
                    <p style="font-size: 16px; margin: 20px 0;">Ciao {user_name},</p>
                    
                    <p style="font-size: 15px; color: {SETERA_COLORS['text_light']}; margin-bottom: 30px;">
                        Il tuo report automatico è pronto! Maya ha analizzato i dati del tuo sistema telefonico e ha generato le seguenti insights:
                    </p>
                    
                    {kpi_cards_html}
                    
                    {charts_html}
                    
                    <div class="insights-section">
                        <h2>📊 Analisi Dettagliata</h2>
                        <div class="insights-content">
                            {format_insights_html(insights)}
                        </div>
                    </div>
                    
                    <div style="margin-top: 40px; padding: 20px; background: {SETERA_COLORS['light']}; border-radius: 8px;">
                        <p style="margin: 0; font-size: 14px; color: {SETERA_COLORS['text_light']};">
                            <strong>💡 Questi dati ti aiuteranno a:</strong><br>
                            📈 Monitorare le performance del sistema • 🎯 Identificare aree di miglioramento<br>
                            📊 Prendere decisioni data-driven • ⚡ Ottimizzare l'efficienza operativa
                        </p>
                    </div>
                </div>
                
                <div class="footer">
                    🤖 Questo report è stato generato automaticamente da Maya Analytics<br>
                    Sistema di intelligenza artificiale per l'analisi dei dati telefonici Setera
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
        
    except Exception as e:
        logger.error(f"❌ Error formatting email content: {str(e)}")
        # Fallback to simple format
        return f"""
        <html>
        <body>
        <h2>🤖 Maya Analytics Report</h2>
        <p>Ciao {user_name},</p>
        <p>Il tuo report è pronto:</p>
        <div style="background: #f5f5f5; padding: 15px; border-radius: 5px;">
        <pre>{insights}</pre>
        </div>
        <p>Generato il: {timestamp}</p>
        </body>
        </html>
        """

def format_insights_html(insights: str) -> str:
    """Convert text insights to formatted HTML with table conversion"""
    if not insights:
        return "<p>⚠️ Insights non disponibili in questo momento.</p>"
    
    # Convert ASCII tables to HTML tables
    lines = insights.split('\n')
    html_parts = []
    in_table = False
    table_rows = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Detect table start (line with | and multiple columns)
        if '|' in line and line.count('|') >= 3:
            if not in_table:
                in_table = True
                table_rows = []
            
            # Skip separator lines (|---|---|)
            if not all(c in '|-: ' for c in line) or line.count('-') < 3:
                # Parse table row
                cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove empty first/last
                if cells:
                    table_rows.append(cells)
        else:
            # End of table
            if in_table and table_rows:
                html_parts.append(convert_table_to_html(table_rows))
                table_rows = []
                in_table = False
            
            # Regular text line
            if line:
                # Format headers
                if line.startswith('🔍') or line.startswith('📊') or line.startswith('🎯') or line.startswith('💡') or line.startswith('⚡') or line.startswith('📈'):
                    html_parts.append(f'<h3 style="margin-top: 25px; margin-bottom: 15px; color: {SETERA_COLORS["primary"]}; font-size: 18px; font-weight: 600;">{line}</h3>')
                elif line.startswith('•') or line.startswith('-'):
                    html_parts.append(f'<p style="margin: 8px 0; padding-left: 20px;">{line}</p>')
                else:
                    html_parts.append(f'<p style="margin: 12px 0;">{line}</p>')
        
        i += 1
    
    # Close any remaining table
    if in_table and table_rows:
        html_parts.append(convert_table_to_html(table_rows))
    
    return '\n'.join(html_parts)

def convert_table_to_html(table_rows: List[List[str]]) -> str:
    """Convert table rows to HTML table"""
    if not table_rows or len(table_rows) < 2:
        return ""
    
    html = '<div class="table-container"><table class="data-table">'
    
    # First row is header
    if table_rows:
        html += '<thead><tr>'
        for cell in table_rows[0]:
            html += f'<th>{cell}</th>'
        html += '</tr></thead>'
    
    # Remaining rows are data
    if len(table_rows) > 1:
        html += '<tbody>'
        for row in table_rows[1:]:
            html += '<tr>'
            for cell in row:
                # Check for status indicators and format
                cell_html = cell
                if '🟢' in cell or 'good' in cell.lower() or 'ok' in cell.lower():
                    cell_html = cell.replace('🟢', '<span class="status-badge status-good">OK</span>')
                elif '🟡' in cell or 'warning' in cell.lower() or 'attenzione' in cell.lower():
                    cell_html = cell.replace('🟡', '<span class="status-badge status-warning">ATTENZIONE</span>')
                elif '🔴' in cell or 'critico' in cell.lower() or 'danger' in cell.lower():
                    cell_html = cell.replace('🔴', '<span class="status-badge status-danger">CRITICO</span>')
                html += f'<td>{cell_html}</td>'
            html += '</tr>'
        html += '</tbody>'
    
    html += '</table></div>'
    return html

# ========================================
# DATA FETCHING
# ========================================

def fetch_xml_data(xml_endpoint: str, xml_token: Optional[str] = None) -> str:
    """Fetch XML data from the provided endpoint"""
    try:
        logger.info(f"📥 Fetching XML data from: {xml_endpoint}")
        
        headers = {'User-Agent': 'Maya-Analytics/1.0'}
        if xml_token:
            # Support different auth methods
            if xml_token.startswith('Bearer '):
                headers['Authorization'] = xml_token
            elif xml_token.startswith('Basic '):
                headers['Authorization'] = xml_token
            else:
                # Assume Bearer token
                headers['Authorization'] = f'Bearer {xml_token}'
        
        response = requests.get(xml_endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        
        xml_content = response.text
        if not xml_content or not xml_content.strip():
            raise Exception("Empty response from XML endpoint")
            
        logger.info(f"✅ XML data fetched successfully ({len(xml_content)} characters)")
        return xml_content
        
    except requests.exceptions.Timeout:
        raise Exception(f"Timeout connecting to {xml_endpoint}")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Cannot connect to {xml_endpoint}")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP error {e.response.status_code} from {xml_endpoint}")
    except Exception as e:
        raise Exception(f"Error fetching XML data: {str(e)}")

# ========================================
# EMAIL SENDING
# ========================================

def send_report_email(user_email: str, user_name: str, html_content: str, user_id: str = None, entity_names: list = None, report_type: str = None):
    """Send report email via email sender Lambda"""
    try:
        logger.info(f"📧 Sending report email to: {user_email}")
        
        # Build subject with date and entity names
        date_str = datetime.utcnow().strftime("%d/%m/%Y")
        
        # Map report types to display names
        report_type_map = {
            'ivr': 'IVR',
            'acd': 'ACD',
            'rulebased': 'RULEBASED',
            'huntgroup': 'HUNTGROUP',
            'user': 'USER'
        }
        report_type_display = report_type_map.get(report_type, '') if report_type else ''
        
        # Format entity names for subject
        entities_str = ""
        if entity_names and len(entity_names) > 0:
            # Filter out "Total" and empty names
            filtered_names = [n for n in entity_names if n and n != 'Total' and n.strip()]
            if filtered_names:
                # Extract display names (after dash if present, e.g., "Others/belal.darwish - Belal Darwish" -> "Belal Darwish")
                display_names = []
                for name in filtered_names[:3]:  # Limit to first 3 to keep subject short
                    if " - " in name:
                        display_name = name.split(" - ")[1]
                        if display_name not in display_names:
                            display_names.append(display_name)
                    elif name not in display_names:
                        display_names.append(name)
                
                if display_names:
                    # Build entities string with report type prefix if available
                    if report_type_display:
                        if len(display_names) == 1:
                            entities_str = f"{report_type_display} '{display_names[0]}'"
                        elif len(display_names) == 2:
                            entities_str = f"{report_type_display} '{display_names[0]}, {display_names[1]}'"
                        else:
                            entities_str = f"{report_type_display} '{display_names[0]}, {display_names[1]}, ...'"
                    else:
                        # Fallback without report type
                        if len(display_names) == 1:
                            entities_str = f"({display_names[0]})"
                        elif len(display_names) == 2:
                            entities_str = f"({display_names[0]}, {display_names[1]})"
                        else:
                            entities_str = f"({display_names[0]}, {display_names[1]}, ...)"
        
        subject = f'🤖 Maya Analytics - Report Automatico del {date_str}'
        if entities_str:
            subject += f' - {entities_str}'
        
        email_payload = {
            'to_email': user_email,
            'subject': subject,
            'html_content': html_content,
            'user_id': user_id
        }
        
        response = lambda_client.invoke(
            FunctionName=EMAIL_SENDER_FUNCTION,
            InvocationType='Event',  # Async
            Payload=json.dumps(email_payload, cls=DecimalEncoder)
        )
        
        logger.info(f"✅ Email queued for sending to {user_email}")
        
    except Exception as e:
        logger.error(f"❌ Error sending email: {str(e)}")
        raise Exception(f"Email sending failed: {str(e)}")

# ========================================
# REPORT STORAGE
# ========================================

def save_report_history(user_id: str, user_data: Dict, insights: str, status: str = 'generated'):
    """Save report to history table"""
    try:
        timestamp = datetime.utcnow().isoformat()
        
        report_item = {
            'user_id': user_id,
            'report_timestamp': timestamp,
            'generated_at': timestamp,
            'status': status,
            'insights_preview': insights[:500] + '...' if len(insights) > 500 else insights,
            'user_email': user_data.get('email', ''),
            'user_name': user_data.get('name', ''),
            'ttl': int((datetime.utcnow() + timedelta(days=90)).timestamp())
        }
        
        reports_table.put_item(Item=report_item)
        logger.info(f"✅ Report history saved for user: {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error saving report history: {str(e)}")

# ========================================
# SCHEDULE CHECKING
# ========================================

def should_generate_report_now(user: Dict) -> bool:
    """Check if report should be generated now based on user schedule"""
    try:
        if not user.get('report_enabled'):
            return False
        
        schedule_str = user.get('report_schedule', '{}')
        if isinstance(schedule_str, str):
            schedule = json.loads(schedule_str)
        else:
            schedule = schedule_str
        
        now = datetime.utcnow()
        frequency = schedule.get('frequency', 'daily')
        time_str = schedule.get('time', '09:00')
        
        # Parse scheduled time
        try:
            hour, minute = map(int, time_str.split(':'))
        except:
            hour, minute = 9, 0
        
        # Check if we're within the scheduled minute
        if now.hour != hour or now.minute != minute:
            return False
        
        if frequency == 'daily':
            return True
        elif frequency == 'weekly':
            day_of_week = schedule.get('day_of_week', '1')  # Monday
            return str(now.weekday() + 1) == str(day_of_week)
        elif frequency == 'monthly':
            day_of_month = schedule.get('day_of_month', '1')
            return str(now.day) == str(day_of_month)
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Error checking schedule for user {user.get('user_id', 'unknown')}: {str(e)}")
        return False

def get_scheduled_users() -> List[Dict]:
    """Get users who should receive reports now
    
    Supports both old format (xml_endpoint directly on user) and new format (connectors array)
    """
    try:
        logger.info("🔍 Checking for scheduled users...")
        
        # Scan all users (end-users don't have report_enabled field, they use connectors)
        response = users_table.scan()
        
        users = response.get('Items', [])
        scheduled_users = []
        
        for user in users:
            # Skip non-end-users (Admin/SuperAdmin/Reseller)
            if user.get('role') != 'User':
                continue
            
            # Check if user has connectors with enabled reports
            connectors = user.get('connectors', [])
            
            # Backward compatibility: check old format (xml_endpoint directly on user)
            if not connectors and user.get('xml_endpoint'):
                # Old format - treat as single connector
                if should_generate_report_now(user):
                    scheduled_users.append(user)
            else:
                # New format - check each connector
                for connector in connectors:
                    if connector.get('report_enabled', True):
                        # Create a user-like dict for this connector
                        connector_user = {
                            **user,
                            'xml_endpoint': connector.get('xml_endpoint', ''),
                            'xml_token': connector.get('xml_token', ''),
                            'report_enabled': connector.get('report_enabled', True),  # Use connector's report_enabled, not user's
                            'report_schedule': connector.get('report_schedule', user.get('report_schedule', '{}')),
                            'connector_id': connector.get('connector_id'),
                            'connector_name': connector.get('name', 'Report')
                        }
                        if should_generate_report_now(connector_user):
                            scheduled_users.append(connector_user)
        
        logger.info(f"📅 Found {len(scheduled_users)} connectors scheduled for reports")
        return scheduled_users
        
    except Exception as e:
        logger.error(f"❌ Error getting scheduled users: {str(e)}")
        return []

# ========================================
# MAIN REPORT GENERATION
# ========================================

def generate_report_for_user(user_data: Dict) -> bool:
    """Generate and send report for a single user"""
    user_id = user_data.get('user_id', 'unknown')
    # Use report_email if present, otherwise fallback to email
    # report_email can be duplicated across users (multiple users can receive reports at same email)
    user_email = user_data.get('report_email', '') or user_data.get('email', '')
    user_name = user_data.get('name', 'Utente')
    
    try:
        logger.info(f"🚀 Starting report generation for user: {user_email}")
        
        # Validate user data
        xml_endpoint = user_data.get('xml_endpoint', '')
        if not xml_endpoint:
            raise Exception("XML endpoint not configured for user")
        
        if not user_email:
            raise Exception("User email not available")
        
        # Fetch XML data
        xml_token = user_data.get('xml_token')
        xml_content = fetch_xml_data(xml_endpoint, xml_token)
        
        # Parse XML data
        parsed_data = parse_xml_report(xml_content)
        
        # Generate insights with Claude
        insights = generate_insights_with_claude(parsed_data)
        
        # Extract report type and entity names from parsed_data for email subject
        report_type = parsed_data.get('report_type', '')
        entity_names = []
        specific_details = parsed_data.get('specific_details', {})
        if specific_details:
            # Try to get full names first (most specific)
            full_names = specific_details.get('unique_full_names', [])
            if full_names:
                entity_names = full_names
            else:
                # Fallback to other name types based on report type
                if report_type == 'user':
                    entity_names = specific_details.get('unique_user_names', [])
                elif report_type == 'acd':
                    entity_names = specific_details.get('unique_grouping_names', [])
                elif report_type == 'huntgroup':
                    entity_names = specific_details.get('unique_huntgroup_names', [])
                elif report_type == 'rulebased':
                    entity_names = specific_details.get('unique_rulebased_names', [])
                elif report_type == 'ivr':
                    entity_names = specific_details.get('unique_ivr_names', [])
        
        # Format email content
        html_content = format_email_content(user_data, insights)
        
        # Send email with entity names and report type
        send_report_email(user_email, user_name, html_content, user_id, entity_names, report_type)
        
        # Save to history
        save_report_history(user_id, user_data, insights, 'sent')
        
        logger.info(f"✅ Report generated and sent successfully for: {user_email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error generating report for user {user_email}: {str(e)}")
        
        # Save error to history
        try:
            save_report_history(user_id, user_data, f"Error: {str(e)}", 'failed')
        except:
            pass
        
        return False

# ========================================
# LAMBDA HANDLER
# ========================================

def lambda_handler(event, context):
    """Main Lambda handler for Maya report generation"""
    logger.info(f"🤖 Maya Report Generator triggered: {json.dumps(event, cls=DecimalEncoder)}")
    
    try:
        trigger_type = event.get('trigger_type', 'schedule_check')
        
        if trigger_type == 'schedule_check':
            # Check for users scheduled to receive reports now
            scheduled_users = get_scheduled_users()
            
            if not scheduled_users:
                logger.info("📅 No users scheduled for reports at this time")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'No reports scheduled',
                        'timestamp': datetime.utcnow().isoformat()
                    }, cls=DecimalEncoder)
                }
            
            # Generate reports for scheduled users
            total_users = len(scheduled_users)
            successful_reports = 0
            failed_reports = 0
            
            for user in scheduled_users:
                try:
                    if generate_report_for_user(user):
                        successful_reports += 1
                    else:
                        failed_reports += 1
                except Exception as e:
                    logger.error(f"❌ Failed to process user {user.get('email', 'unknown')}: {str(e)}")
                    failed_reports += 1
            
            result = {
                'message': f'Reports processed for {total_users} users',
                'successful': successful_reports,
                'failed': failed_reports,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"📊 Report generation summary: {json.dumps(result)}")
            
            return {
                'statusCode': 200,
                'body': json.dumps(result, cls=DecimalEncoder)
            }
            
        elif trigger_type == 'manual_test':
            # Manual test trigger for specific user
            user_id = event.get('user_id')
            if not user_id:
                raise Exception("user_id required for manual test")
            
            # Get user data
            result = users_table.query(
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': user_id}
            )
            
            if not result.get('Items'):
                raise Exception(f"User not found: {user_id}")
            
            user_data = result['Items'][0]
            success = generate_report_for_user(user_data)
            
            return {
                'statusCode': 200 if success else 500,
                'body': json.dumps({
                    'message': 'Manual test completed',
                    'success': success,
                    'user_email': user_data.get('email'),
                    'timestamp': datetime.utcnow().isoformat()
                }, cls=DecimalEncoder)
            }
            
        else:
            raise Exception(f"Unknown trigger type: {trigger_type}")
            
    except Exception as e:
        logger.error(f"❌ Error in Maya report generator: {str(e)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }, cls=DecimalEncoder)
        }

# ========================================
# TESTING UTILITIES
# ========================================

def test_xml_parsing():
    """Test function for XML parsing"""
    sample_ivr_xml = """<?xml version="1.0"?>
    <root>
        <data>
            <report>
                <date__groupsobjects>
                    <period>Total</period>
                    <type>total</type>
                    <incoming_total_handled_by_ivr>100</incoming_total_handled_by_ivr>
                    <incoming_connected>85</incoming_connected>
                    <incoming_not_connected>15</incoming_not_connected>
                    <incoming_average_call_duration_for_ivr>25</incoming_average_call_duration_for_ivr>
                </date__groupsobjects>
            </report>
        </data>
    </root>"""
    
    try:
        result = parse_xml_report(sample_ivr_xml)
        print("✅ XML Parsing Test Successful")
        print(json.dumps(result, indent=2, cls=DecimalEncoder))
        return True
    except Exception as e:
        print(f"❌ XML Parsing Test Failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Run tests when executed directly
    test_xml_parsing()