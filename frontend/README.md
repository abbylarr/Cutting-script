# Filmlist Frontend

React-based frontend for the Filmlist application - automatic montage list generation from video files.

## Features

### Video Upload and Project Creation (Subtask 14.1) ✅
- **Video File Upload**: Drag-and-drop interface for video files with progress tracking
- **Film Metadata Form**: Comprehensive form for film information including:
  - Title, production company, year, country
  - Screenwriters and copyright holders (tag-based input)
  - Duration, episodes count, format, color type
  - Media carrier and language settings
- **Project Settings**: 
  - Timecode start selection (01:00:00:00 or 00:00:00:00)
  - Standard selection (ГФФ or Красногорский) 
  - Frame rate configuration (23.976 to 60 fps)
- **SRT/Auto-transcription Mode**: Toggle between automatic transcription and SRT file upload
- **Form Validation**: Required field validation and file type checking

### Processing Progress Visualization (Subtask 14.2) ✅
- **Animated Progress Interface**: Real-time progress bar with smooth animations
- **Step Descriptions**: "Magical" processing descriptions with emojis and user-friendly text
- **Timeline Visualization**: Interactive timeline showing completed, current, and pending steps
- **ETA Display**: Time estimates for each processing step
- **Real-time Updates**: WebSocket integration with polling fallback
- **Auto-redirect**: Automatic navigation to editor when processing completes
- **Error Handling**: Graceful error states with retry options

### Montage Table Editor Interface (Subtask 14.3) ✅
- **Interactive Table Component**: Fully editable montage table with inline editing
- **Video Player Integration**: ReactPlayer with timeline synchronization and seeking
- **Shot Type Selection**: Color-coded tags with dropdown selection (Дальний, Общий, Средний, Крупный, Деталь)
- **Speaker Management**: Clickable speaker tags with inline renaming functionality
- **Real-time Editing**: Live cell editing for timecodes, descriptions, and dialogues
- **Save/Export Functionality**: Save changes to backend and export DOCX files
- **Timeline Synchronization**: Click table rows to seek video to corresponding timecode
- **Change Tracking**: Visual indicators for unsaved changes

### Project Sidebar and User Account Interface (Subtask 14.4) ✅
- **Project Listing**: Complete project management with search and filtering
- **User Account Panel**: Balance display with top-up functionality
- **Search and Filtering**: Real-time project search and status-based filtering
- **Project Management**: Open, duplicate, and delete project actions
- **Status Indicators**: Visual status badges (Готов, Обработка)
- **Navigation Integration**: Seamless navigation between projects and editor
- **Responsive Design**: Professional sidebar layout with hover effects
- **Empty States**: User-friendly messages for no projects or search results

## Technology Stack

- **React 18** with TypeScript
- **Styled Components** for styling
- **React Router** for navigation
- **React Dropzone** for file uploads
- **Axios** for API communication
- **Testing Library** for component testing

## Project Structure

```
frontend/
├── src/
│   ├── components/           # React components
│   │   ├── VideoUpload.tsx          # Main upload interface ✅
│   │   ├── FilmMetadataForm.tsx     # Film metadata form ✅
│   │   ├── ProjectSettingsForm.tsx  # Project settings ✅
│   │   ├── Login.tsx                # Authentication ✅
│   │   ├── Sidebar.tsx              # Project sidebar ✅
│   │   ├── ProcessingProgress.tsx   # Progress visualization 🚧
│   │   ├── MontageEditor.tsx        # Table editor 🚧
│   │   └── __tests__/               # Component tests ✅
│   ├── services/
│   │   └── api.ts            # API service layer ✅
│   ├── types/
│   │   └── index.ts          # TypeScript type definitions ✅
│   ├── App.tsx               # Main application component ✅
│   └── index.tsx             # Application entry point ✅
├── public/
│   └── index.html            # HTML template ✅
├── package.json              # Dependencies and scripts ✅
└── tsconfig.json             # TypeScript configuration ✅
```

## Installation and Setup

1. **Install dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Environment Configuration**:
   Create a `.env` file in the frontend directory:
   ```
   REACT_APP_API_URL=http://localhost:8000/api/v1
   ```

3. **Start development server**:
   ```bash
   npm start
   ```

4. **Run tests**:
   ```bash
   npm test
   ```

5. **Build for production**:
   ```bash
   npm run build
   ```

## Component Documentation

### VideoUpload Component
Main interface for video upload and project creation. Features:
- Drag-and-drop video file upload
- Mode selection (auto-transcription vs SRT upload)
- Integrated film metadata and project settings forms
- Upload progress tracking
- Form validation

### FilmMetadataForm Component
Comprehensive form for film metadata with:
- Text inputs for basic information
- Tag-based inputs for arrays (screenwriters, copyright holders)
- Select dropdowns for predefined options
- Proper validation and error handling

### ProjectSettingsForm Component  
Configuration interface for:
- Timecode start point toggle
- Standard selection toggle
- Frame rate dropdown with common options
- Informational help text

## API Integration

The frontend communicates with the FastAPI backend through the `apiService`:

- **Authentication**: Login, register, user management
- **Upload**: Video and SRT file uploads with progress tracking
- **Tasks**: Status monitoring, montage updates, project saving
- **Projects**: CRUD operations for film projects
- **Billing**: Balance checking and payment processing

## Testing

Component tests cover:
- Rendering and UI elements
- User interactions (form inputs, toggles, buttons)
- State management and prop handling
- API integration (mocked)
- Form validation and error handling

Run tests with: `npm test -- --watchAll=false`

## Requirements Compliance

### Requirement 1.1 ✅
- Video file upload with task creation
- File validation and progress tracking

### Requirement 1.2 ✅  
- Auto-transcription mode selection
- Full pipeline configuration

### Requirement 1.3 ✅
- SRT file upload mode
- Music detection configuration

### Requirement 2.1 ✅
- Animated progress interface with step descriptions
- "Magical" processing descriptions with time estimates

### Requirement 2.2 ✅  
- Real-time progress updates with WebSocket/polling fallback
- Time estimates and ETA display

### Requirement 2.3 ✅
- Continuous processing in background
- Automatic redirect on completion

### Requirement 3.1 ✅
- Interactive table with video player synchronization
- Click table rows to seek video to corresponding timecode

### Requirement 3.2 ✅
- Color-coded shot type tags (Дальний, Общий, Средний, Крупный, Деталь)
- Dropdown selection for shot type changes

### Requirement 3.3 ✅
- Clickable speaker tags with inline renaming
- Speaker management and selection interface

### Requirement 3.4 ✅
- Real-time change tracking and save functionality
- Automatic DOCX file generation and export

### Requirement 4.1 ✅
- Complete film metadata form
- All required fields implemented

### Requirement 8.1 ✅
- Timecode start selection (01:00:00:00 or 00:00:00:00)

### Requirement 8.2 ✅
- Standard selection (ГФФ or Красногорский)

## Next Steps

1. **Subtask 14.2**: Implement animated progress visualization with real-time updates
2. **Subtask 14.3**: Create interactive montage table editor with video player integration  
3. **Subtask 14.4**: Complete project sidebar with search, filtering, and management features

## Notes

- The frontend is designed to work with the existing FastAPI backend
- All components are responsive and follow accessibility best practices
- TypeScript provides type safety throughout the application
- Styled Components enable consistent theming and responsive design