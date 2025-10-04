# Gmail Labeler React App

A modern, responsive React application for intelligent email labeling powered by AI.

## Features

- 🎨 **Modern Gmail-like UI** - Clean, intuitive interface matching Gmail's design language
- 🤖 **AI-Powered Suggestions** - Get intelligent label suggestions based on email content
- 🏷️ **Smart Labeling** - Organize emails with custom labels and colors
- ⚡ **Real-time Updates** - Instant feedback and smooth interactions
- 📱 **Responsive Design** - Works seamlessly on desktop and mobile
- ⭐ **Email Management** - Star important emails, mark as read/unread
- 🔍 **Search & Filter** - Quickly find emails by content or labels
- 💼 **Batch Operations** - Select multiple emails for bulk actions

## Getting Started

### Prerequisites

- Node.js 14+ and npm

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm start
```

3. Open [http://localhost:3000](http://localhost:3000) in your browser

## Available Scripts

- `npm start` - Runs the app in development mode
- `npm test` - Launches the test runner
- `npm run build` - Builds the app for production
- `npm run eject` - Ejects from Create React App (one-way operation)

## Technology Stack

- **React 18** with TypeScript for type-safe development
- **Tailwind CSS** for modern, utility-first styling
- **Lucide React** for beautiful, consistent icons
- **Axios** for API requests (ready for backend integration)

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── EmailSidebar.tsx    # Navigation sidebar with labels
│   ├── EmailListItem.tsx   # Individual email in list view
│   └── EmailDetail.tsx     # Full email view with actions
├── data/               # Mock data and API logic
│   └── mockData.ts         # Sample emails and labels
├── types/              # TypeScript type definitions
│   └── email.ts            # Email and Label interfaces
├── App.tsx             # Main application component
└── index.tsx           # Application entry point
```

## Features in Detail

### Email List View
- Gmail-style compact email cards
- Quick actions (star, select, get suggestions)
- Inline label suggestions with accept/reject
- Unread indicators and timestamps

### Email Detail View
- Full email content with formatting
- Label management (add/remove)
- AI-powered label suggestions
- Back to inbox navigation

### Sidebar
- Inbox with unread count
- Custom labels with colors
- Active label highlighting
- Settings access

### AI Suggestions
- Context-aware label recommendations
- Based on email content, subject, and sender
- One-click accept/reject actions
- Visual feedback during loading

## Backend Integration

This app is ready to connect to a backend API. Update the mock data functions in `src/data/mockData.ts` with actual API calls using axios.

Example API endpoints needed:
- `GET /api/emails` - Fetch emails
- `GET /api/labels` - Fetch labels
- `POST /api/emails/:id/labels` - Add label to email
- `DELETE /api/emails/:id/labels/:label` - Remove label
- `POST /api/emails/:id/suggestions` - Get AI suggestions

## Customization

### Colors
Update Tailwind config in `tailwind.config.js` to customize the color scheme.

### Labels
Modify `src/data/mockData.ts` to add/remove default labels.

### AI Logic
Implement custom AI suggestion logic in `handleGetSuggestions` function in `App.tsx`.

## Production Build

To create an optimized production build:

```bash
npm run build
```

This creates a `build` folder with optimized static files ready for deployment.

## Deployment

The app can be deployed to any static hosting service:
- Vercel
- Netlify
- GitHub Pages
- AWS S3 + CloudFront
- Firebase Hosting

## License

MIT

## Support

For issues or questions, please open an issue in the repository.
