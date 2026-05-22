# Public Opinion Analysis Expert Template Documentation

## 1. Template Overview

### Introduction
The Public Opinion Analysis Expert is an intelligent public opinion analysis system built on the PydanticAI framework. It automatically collects, analyzes, and summarizes online public opinion, providing real-time monitoring and analysis services for enterprises and organizations.

### Use Cases
- Brand reputation monitoring and management
- Crisis early warning and public opinion surveillance
- Competitor analysis and market research
- Public opinion collection and analysis
- Social media sentiment tracking

### Core Features
- Automated information collection and filtering
- Intelligent sentiment analysis and classification
- Public opinion trend forecasting
- Visual report generation

## 2. Technical Architecture

### Framework
- **Framework**: PydanticAI
- **Agent Type**: Single-Agent architecture
- **Core Capabilities**: Integrated LLM, search tools, and Sandbox environment

### Agent Architecture
The system adopts a single-Agent design with multiple capabilities:
- Information retrieval (via search tools)
- Data analysis (via Sandbox environment)
- Natural language understanding and generation (via LLM)

### Technical Requirements
- Supports mainstream large language models (user-selectable)
- Requires search API access configuration
- Requires Sandbox environment support

## 3. Feature Description

### Main Functional Modules

**Information Collection Module**
- Multi-source data crawling (news, social media, forums, etc.)
- Intelligent keyword matching
- Real-time data updates

**Analysis and Processing Module**
- Sentiment analysis (positive/negative/neutral)
- Hot topic extraction
- Dissemination path tracking
- Influence assessment

**Report Generation Module**
- Structured analysis reports
- Data visualization charts
- Trend forecasting and recommendations

### Agent Capabilities
1. **Autonomous Search**: Automatically retrieves relevant information based on keywords
2. **Intelligent Analysis**: Performs sentiment analysis and classification on massive amounts of information
3. **Code Execution**: Executes data processing and visualization code in the Sandbox
4. **Report Generation**: Automatically generates professional public opinion analysis reports

### Workflow
```
User query input → Agent executes search → Information collection →
Data cleaning → Sentiment analysis → Sandbox data processing →
Generate visualization charts → Output analysis report
```

## 4. Configuration Guide

### Console Configuration

**Model Configuration**
- Select a suitable large language model in the AgentRun console
- Models with long context support are recommended for handling large volumes of public opinion data
- Choose models with different parameters based on analysis precision requirements

**Sandbox Configuration**
- Enable the Sandbox environment
- Configure allowed Python libraries (e.g., pandas, matplotlib)
- Set execution time and resource limits

## 5. Usage Examples

### Application Scenarios

**Scenario 1: Brand Reputation Monitoring**
```
User input: Analyze online public opinion about "XX Brand" over the past week
```

**Agent Execution Flow:**
1. Use search tools to retrieve relevant news, social media posts, and forum threads
2. Extract key information and comment content
3. Perform sentiment analysis and classification
4. Generate trend charts in the Sandbox
5. Output a complete analysis report

**Output Example:**
```markdown
# XX Brand Public Opinion Analysis Report (2024.XX.XX - 2024.XX.XX)

## Overview
- Total information volume: 1,250 entries
- Positive sentiment: 65%
- Negative sentiment: 15%
- Neutral sentiment: 20%

## Hot Topics
1. New product launch (popularity: 85%)
2. After-sales service (popularity: 45%)
3. Price adjustment (popularity: 30%)

## Sentiment Trend Analysis
[Trend Charts]

## Key Concerns
- 3 potential crisis points identified
- Recommended countermeasures...
```

## 6. FAQ

### Q1: What if search results are inaccurate?
- Optimize search keyword settings in the console
- Adjust search scope and time window
- Increase search depth for more results

### Q2: Analysis is slow?
- Choose a higher-performance model
- Reduce the number of search results
- Use fast analysis mode

### Q3: How to improve analysis accuracy?
- Choose a model specifically optimized for sentiment analysis
- Adjust sentiment determination thresholds
- Enable deep analysis mode

### Important Notes
1. **Data Privacy**: Ensure no sensitive personal information is analyzed
2. **Search Quota**: Be mindful of search API call limits
3. **Timeliness**: Public opinion data is time-sensitive; regular analysis updates are recommended
4. **Model Selection**: Different models vary significantly in sentiment analysis capabilities; testing before selection is advised
5. **Visualization Limits**: Chart generation in the Sandbox is subject to resource constraints; avoid processing extremely large datasets

---

Deploy and customize your public opinion analysis system quickly through the AgentRun console's visual configuration, with no coding required.
