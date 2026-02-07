import { EventEmitter } from "events";
import { google } from "googleapis";

export interface ChatMessage {
  author: string;
  message: string;
  timestamp: Date;
}

export class YouTubeChatService extends EventEmitter {
  private liveChatId: string;
  private youtubeClient: any;

  constructor(apiKey: string, liveChatId: string) {
    super();
    this.liveChatId = liveChatId;
    this.youtubeClient = google.youtube({ version: "v3", auth: apiKey });
  }

  async start() {
    console.log("YouTube Chat Service started...");
  }

  async sendMessage(message: string) {
    console.log("Sending message:", message);
  }

  private handleIncomingMessage(rawMessage: any) {
    const chatMessage: ChatMessage = {
      author: rawMessage.authorDetails.displayName,
      message: rawMessage.snippet.displayMessage,
      timestamp: new Date(rawMessage.snippet.publishedAt),
    };
    this.emit("message", chatMessage);
  }
}

