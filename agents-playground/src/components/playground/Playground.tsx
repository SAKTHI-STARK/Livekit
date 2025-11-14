"use client";

import { LoadingSVG } from "@/components/button/LoadingSVG";
import { ChatMessageType } from "@/components/chat/ChatTile";
import { ColorPicker } from "@/components/colorPicker/ColorPicker";
import { AudioInputTile } from "@/components/config/AudioInputTile";
import { ConfigurationPanelItem } from "@/components/config/ConfigurationPanelItem";
import { NameValueRow } from "@/components/config/NameValueRow";
import { PlaygroundHeader } from "@/components/playground/PlaygroundHeader";
import {
  PlaygroundTab,
  PlaygroundTabbedTile,
  PlaygroundTile,
} from "@/components/playground/PlaygroundTile";
import { useConfig } from "@/hooks/useConfig";
import { TranscriptionTile } from "@/transcriptions/TranscriptionTile";
import {
  BarVisualizer,
  useConnectionState,
  useDataChannel,
  useLocalParticipant,
  useRoomInfo,
  useTracks,
  useVoiceAssistant,
  useRoomContext,
  useParticipantAttributes,
} from "@livekit/components-react";
import {
  ConnectionState,
  LocalParticipant,
  Track,
  RpcError,
  RpcInvocationData,
} from "livekit-client";
import { QRCodeSVG } from "qrcode.react";
import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import tailwindTheme from "../../lib/tailwindTheme.preval";
import { EditableNameValueRow } from "@/components/config/NameValueRow";
import { AttributesInspector } from "@/components/config/AttributesInspector";
import { RpcPanel } from "./RpcPanel";

export interface PlaygroundProps {
  logo?: ReactNode;
  themeColors: string[];
  onConnect: (connect: boolean, opts?: { token: string; url: string }) => void;
}

const headerHeight = 56;

export default function Playground({
  logo,
  themeColors,
  onConnect,
}: PlaygroundProps) {
  const { config, setUserSettings } = useConfig();
  const { name } = useRoomInfo();
  const [transcripts, setTranscripts] = useState<ChatMessageType[]>([]);
  const { localParticipant } = useLocalParticipant();
  const voiceAssistant = useVoiceAssistant();
  const roomState = useConnectionState();
  const tracks = useTracks();
  const room = useRoomContext();

  const [rpcMethod, setRpcMethod] = useState("");
  const [rpcPayload, setRpcPayload] = useState("");
  const [rpcResponse, setRpcResponse] = useState<string | null>(null);
  const [rpcError, setRpcError] = useState<string | null>(null);

  /* --------------------------------------------------------------------- *
   *  1. ENABLE MIC ON CONNECT
   * --------------------------------------------------------------------- */
  useEffect(() => {
    console.log("[Playground] roomState →", roomState);
    if (roomState === ConnectionState.Connected && localParticipant) {
      console.log("[Playground] Enabling mic:", config.settings.inputs.mic);
      localParticipant.setMicrophoneEnabled(config.settings.inputs.mic).catch((err) => {
        console.error("[Playground] Failed to set mic:", err);
      });
    }
  }, [config.settings.inputs.mic, localParticipant, roomState]);

  /* --------------------------------------------------------------------- *
   *  2. REGISTER CLIENT-SIDE RPC METHOD (getUserLocation) – CLIENT ← AGENT
   * --------------------------------------------------------------------- */
  useEffect(() => {
  if (!localParticipant) {
    console.log("[RPC] No localParticipant – skip");
    return;
  }

  const handleSentLink = async () => {
    try {
      if (typeof window !== "undefined") {
        window.alert("Agent send a renewal link!");
      }
      return "ok"; // agent expects string return
    } catch (err) {
      throw new RpcError(1, "Alert failed");
    }
  };

  console.log("[RPC] Registering sent_link");
  try {
    localParticipant.registerRpcMethod("sent_link", handleSentLink);
  } catch (err) {
    console.error("[RPC] Failed to register sent_link:", err);
  }

  return () => {
    console.log("[RPC] Unregistering sent_link");
    try {
      localParticipant.unregisterRpcMethod("sent_link");
    } catch (err) {
      console.warn("[RPC] unregister error:", err);
    }
  };
}, [localParticipant]);


  /* --------------------------------------------------------------------- *
   *  3. FIND TRACKS
   * --------------------------------------------------------------------- */
  const agentVideoTrack = tracks.find(
    (t) =>
      t.publication.kind === Track.Kind.Video && t.participant.isAgent,
  );

  const localTracks = tracks.filter(
    ({ participant }) => participant instanceof LocalParticipant,
  );
  const localCameraTrack = localTracks.find(
    ({ source }) => source === Track.Source.Camera,
  );
  const localScreenTrack = localTracks.find(
    ({ source }) => source === Track.Source.ScreenShare,
  );
  const localMicTrack = localTracks.find(
    ({ source }) => source === Track.Source.Microphone,
  );

  /* --------------------------------------------------------------------- *
   *  4. DATA CHANNEL (transcription)
   * --------------------------------------------------------------------- */
  const onDataReceived = useCallback((msg: any) => {
    console.log("[DataChannel] raw →", msg);
    if (msg.topic === "transcription") {
      try {
        const decoded = JSON.parse(new TextDecoder("utf-8").decode(msg.payload));
        console.log("[DataChannel] transcription →", decoded);
        const timestamp = decoded.timestamp > 0 ? decoded.timestamp : Date.now();
        setTranscripts((prev) => [
          ...prev,
          {
            name: "You",
            message: decoded.text,
            timestamp,
            isSelf: true,
          },
        ]);
      } catch (e) {
        console.error("[DataChannel] JSON parse error:", e);
      }
    }
  }, []);

  useDataChannel(onDataReceived);

  /* --------------------------------------------------------------------- *
   *  5. THEME COLOR
   * --------------------------------------------------------------------- */
  useEffect(() => {
    console.log("[Theme] Updating --lk-theme-color →", config.settings.theme_color);
    document.body.style.setProperty(
      "--lk-theme-color",
      // @ts-ignore
      tailwindTheme.colors[config.settings.theme_color]["500"],
    );
    document.body.style.setProperty(
      "--lk-drop-shadow",
      `var(--lk-theme-color) 0px 0px 18px`,
    );
  }, [config.settings.theme_color]);

  /* --------------------------------------------------------------------- *
   *  6. AUDIO VISUALIZER
   * --------------------------------------------------------------------- */
  const audioTileContent = useMemo(() => {
    const disconnected = (
      <div className="flex flex-col items-center justify-center gap-2 text-gray-700 text-center w-full">
        No agent audio track. Connect to get started.
      </div>
    );

    const waiting = (
      <div className="flex flex-col items-center gap-2 text-gray-700 text-center w-full">
        <LoadingSVG />
        Waiting for agent audio track…
      </div>
    );

    const visualizer = (
      <div
        className={`flex items-center justify-center w-full h-48 [--lk-va-bar-width:30px] [--lk-va-bar-gap:20px] [--lk-fg:var(--lk-theme-color)]`}
      >
        <BarVisualizer
          state={voiceAssistant.state}
          trackRef={voiceAssistant.audioTrack}
          barCount={5}
          options={{ minHeight: 20 }}
        />
      </div>
    );

    if (roomState === ConnectionState.Disconnected) return disconnected;
    if (!voiceAssistant.audioTrack) return waiting;
    return visualizer;
  }, [voiceAssistant.audioTrack, voiceAssistant.state, roomState]);

  /* --------------------------------------------------------------------- *
   *  7. CHAT TILE
   * --------------------------------------------------------------------- */
  const chatTileContent = useMemo(() => {
    if (voiceAssistant.agent) {
      return (
        <TranscriptionTile
          agentAudioTrack={voiceAssistant.audioTrack}
          accentColor={config.settings.theme_color}
        />
      );
    }
    return <></>;
  }, [config.settings.theme_color, voiceAssistant.audioTrack, voiceAssistant.agent]);

  /* --------------------------------------------------------------------- *
   *  8. CLIENT → AGENT RPC CALL
   * --------------------------------------------------------------------- */
  const handleRpcCall = useCallback(async () => {
    if (!voiceAssistant.agent || !room) {
      const err = "No agent or room available";
      console.error("[RPC] →→→", err);
      setRpcError(err);
      return;
    }

    setRpcResponse(null);
    setRpcError(null);

    let payloadObj: any = {};
    if (rpcPayload.trim()) {
      try {
        payloadObj = JSON.parse(rpcPayload);
      } catch (e) {
        console.error("[RPC] Invalid JSON payload:", e);
        setRpcError("Invalid JSON in payload");
        return;
      }
    }

    console.log("[RPC] →→→ Calling agent RPC", {
      method: rpcMethod,
      destination: voiceAssistant.agent.identity,
      payload: payloadObj,
    });

    try {
      const response = await room.localParticipant.performRpc({
        destinationIdentity: voiceAssistant.agent.identity,
        method: rpcMethod,
        payload: payloadObj,
      });

      console.log("[RPC] ←←← Response:", response);
      setRpcResponse(typeof response === "string" ? response : JSON.stringify(response, null, 2));
    } catch (err: any) {
      console.error("[RPC] ←←← ERROR:", err);
      setRpcError(err?.message ?? String(err));
    }
  }, [room, rpcMethod, rpcPayload, voiceAssistant.agent]);

  /* --------------------------------------------------------------------- *
   *  9. AGENT ATTRIBUTES
   * --------------------------------------------------------------------- */
  const agentAttributes = useParticipantAttributes({
    participant: voiceAssistant.agent,
  });

  /* --------------------------------------------------------------------- *
   *  10. SETTINGS TILE (with RPC panel + response UI)
   * --------------------------------------------------------------------- */
  const settingsTileContent = useMemo(() => {
    return (
      <div className="flex flex-col h-full w-full items-start overflow-y-auto">
        {config.description && (
          <ConfigurationPanelItem title="Description">
            {config.description}
          </ConfigurationPanelItem>
        )}

        <ConfigurationPanelItem title="Room">
          <div className="flex flex-col gap-2">
            <EditableNameValueRow
              name="Room name"
              value={
                roomState === ConnectionState.Connected
                  ? name
                  : config.settings.room_name
              }
              valueColor={`${config.settings.theme_color}-500`}
              onValueChange={(value) => {
                const newSettings = { ...config.settings };
                newSettings.room_name = value;
                setUserSettings(newSettings);
              }}
              placeholder="Auto"
              editable={roomState !== ConnectionState.Connected}
            />
            <NameValueRow
              name="Status"
              value={
                roomState === ConnectionState.Connecting ? (
                  <LoadingSVG diameter={16} strokeWidth={2} />
                ) : (
                  roomState.charAt(0).toUpperCase() + roomState.slice(1)
                )
              }
              valueColor={
                roomState === ConnectionState.Connected
                  ? `${config.settings.theme_color}-500`
                  : "gray-500"
              }
            />
          </div>
        </ConfigurationPanelItem>

        <ConfigurationPanelItem title="Agent">
          <div className="flex flex-col gap-2">
            <EditableNameValueRow
              name="Agent name"
              value={
                roomState === ConnectionState.Connected
                  ? config.settings.agent_name || "None"
                  : config.settings.agent_name || ""
              }
              valueColor={`${config.settings.theme_color}-500`}
              onValueChange={(value) => {
                const newSettings = { ...config.settings };
                newSettings.agent_name = value;
                setUserSettings(newSettings);
              }}
              placeholder="None"
              editable={roomState !== ConnectionState.Connected}
            />
            <NameValueRow
              name="Identity"
              value={
                voiceAssistant.agent ? (
                  voiceAssistant.agent.identity
                ) : roomState === ConnectionState.Connected ? (
                  <LoadingSVG diameter={12} strokeWidth={2} />
                ) : (
                  "No agent connected"
                )
              }
              valueColor={
                voiceAssistant.agent
                  ? `${config.settings.theme_color}-500`
                  : "gray-500"
              }
            />
            {roomState === ConnectionState.Connected &&
              voiceAssistant.agent && (
                <AttributesInspector
                  attributes={Object.entries(
                    agentAttributes.attributes || {},
                  ).map(([key, value], index) => ({
                    id: `agent-attr-${index}`,
                    key,
                    value: String(value),
                  }))}
                  onAttributesChange={() => {}}
                  themeColor={config.settings.theme_color}
                  disabled={true}
                />
              )}
            <p className="text-xs text-gray-500 text-right">
              Set an agent name to use{" "}
              <a
                href="https://docs.livekit.io/agents/worker/dispatch#explicit"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-gray-300 underline"
              >
                explicit dispatch
              </a>
              .
            </p>
          </div>
        </ConfigurationPanelItem>

        <ConfigurationPanelItem title="User">
          <div className="flex flex-col gap-2">
            <EditableNameValueRow
              name="Name"
              value={localParticipant?.name || config.settings.participant_name || ""}
              valueColor={`${config.settings.theme_color}-500`}
              onValueChange={(value) => {
                const newSettings = { ...config.settings };
                newSettings.participant_name = value;
                setUserSettings(newSettings);
                if (roomState === ConnectionState.Connected && localParticipant) {
                  localParticipant.setName(value);
                }
              }}
              placeholder="Auto"
              editable={true}
            />
            <EditableNameValueRow
              name="Identity"
              value={
                roomState === ConnectionState.Connected
                  ? localParticipant?.identity || ""
                  : config.settings.participant_id || ""
              }
              valueColor={`${config.settings.theme_color}-500`}
              onValueChange={(value) => {
                const newSettings = { ...config.settings };
                newSettings.participant_id = value;
                setUserSettings(newSettings);
              }}
              placeholder="Auto"
              editable={roomState !== ConnectionState.Connected}
            />
            <AttributesInspector
              attributes={config.settings.attributes || []}
              onAttributesChange={(newAttributes) => {
                const newSettings = { ...config.settings };
                newSettings.attributes = newAttributes;
                setUserSettings(newSettings);
              }}
              metadata={config.settings.metadata}
              onMetadataChange={(metadata) => {
                const newSettings = { ...config.settings };
                newSettings.metadata = metadata;
                setUserSettings(newSettings);
              }}
              themeColor={config.settings.theme_color}
              disabled={false}
              connectionState={roomState}
            />
          </div>
        </ConfigurationPanelItem>

        {/* RPC PANEL */}
        {roomState === ConnectionState.Connected && voiceAssistant.agent && (
          <ConfigurationPanelItem title="RPC (Client → Agent)">
            <RpcPanel
              config={config}
              rpcMethod={rpcMethod}
              rpcPayload={rpcPayload}
              setRpcMethod={setRpcMethod}
              setRpcPayload={setRpcPayload}
              handleRpcCall={handleRpcCall}
            />

            {rpcResponse && (
              <div className="mt-2 p-2 bg-gray-800 rounded text-xs whitespace-pre-wrap">
                <strong>Response:</strong>
                <pre>{rpcResponse}</pre>
              </div>
            )}
            {rpcError && (
              <div className="mt-2 p-2 bg-red-900 rounded text-xs">
                <strong>Error:</strong> {rpcError}
              </div>
            )}
          </ConfigurationPanelItem>
        )}

        {localMicTrack && (
          <ConfigurationPanelItem
            title="Microphone"
            source={Track.Source.Microphone}
          >
            <AudioInputTile trackRef={localMicTrack} />
          </ConfigurationPanelItem>
        )}

        <div className="w-full">
          <ConfigurationPanelItem title="Color">
            <ColorPicker
              colors={themeColors}
              selectedColor={config.settings.theme_color}
              onSelect={(color) => {
                const userSettings = { ...config.settings };
                userSettings.theme_color = color;
                setUserSettings(userSettings);
              }}
            />
          </ConfigurationPanelItem>
        </div>

        {config.show_qr && (
          <div className="w-full">
            <ConfigurationPanelItem title="QR Code">
              <QRCodeSVG value={window.location.href} width="128" />
            </ConfigurationPanelItem>
          </div>
        )}
      </div>
    );
  }, [
    config,
    roomState,
    localParticipant,
    name,
    localMicTrack,
    themeColors,
    setUserSettings,
    voiceAssistant.agent,
    agentAttributes,
    rpcMethod,
    rpcPayload,
    handleRpcCall,
    rpcResponse,
    rpcError,
  ]);

  /* --------------------------------------------------------------------- *
   *  11. MOBILE TABS
   * --------------------------------------------------------------------- */
  const mobileTabs: PlaygroundTab[] = [];

  if (config.settings.outputs.audio) {
    mobileTabs.push({
      title: "Audio",
      content: (
        <PlaygroundTile className="w-full h-full grow" childrenClassName="justify-center">
          {audioTileContent}
        </PlaygroundTile>
      ),
    });
  }

  if (config.settings.chat) {
    mobileTabs.push({
      title: "Chat",
      content: chatTileContent,
    });
  }

  mobileTabs.push({
    title: "Settings",
    content: (
      <PlaygroundTile
        padding={false}
        backgroundColor="gray-950"
        className="h-full w-full basis-1/4 items-start overflow-y-auto flex"
        childrenClassName="h-full grow items-start"
      >
        {settingsTileContent}
      </PlaygroundTile>
    ),
  });

  /* --------------------------------------------------------------------- *
   *  12. RENDER
   * --------------------------------------------------------------------- */
  return (
    <>
      <PlaygroundHeader
        title={config.title}
        logo={logo}
        githubLink={config.github_link}
        height={headerHeight}
        accentColor={config.settings.theme_color}
        connectionState={roomState}
        onConnectClicked={() => onConnect(roomState === ConnectionState.Disconnected)}
      />
      <div
        className={`flex gap-4 py-4 grow w-full selection:bg-${config.settings.theme_color}-900`}
        style={{ height: `calc(100% - ${headerHeight}px)` }}
      >
        {/* Mobile */}
        <div className="flex flex-col grow basis-1/2 gap-4 h-full lg:hidden">
          <PlaygroundTabbedTile
            className="h-full"
            tabs={mobileTabs}
            initialTab={mobileTabs.length - 1}
          />
        </div>

        {/* Desktop – Audio */}
        <div
          className={`flex-col grow basis-1/2 gap-4 h-full hidden lg:${
            !config.settings.outputs.audio && !config.settings.outputs.video
              ? "hidden"
              : "flex"
          }`}
        >
          {config.settings.outputs.audio && (
            <PlaygroundTile
              title="Agent Audio"
              className="w-full h-full grow"
              childrenClassName="justify-center"
            >
              {audioTileContent}
            </PlaygroundTile>
          )}
        </div>

        {/* Desktop – Chat */}
        {config.settings.chat && (
          <PlaygroundTile
            title="Chat"
            className="h-full grow basis-1/4 hidden lg:flex"
          >
            {chatTileContent}
          </PlaygroundTile>
        )}

        {/* Desktop – Settings */}
        <PlaygroundTile
          padding={false}
          backgroundColor="gray-950"
          className="h-full w-full basis-1/4 items-start overflow-y-auto hidden max-w-[480px] lg:flex"
          childrenClassName="h-full grow items-start"
        >
          {settingsTileContent}
        </PlaygroundTile>
      </div>
    </>
  );
}