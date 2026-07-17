local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Players = game:GetService("Players")
local VirtualInputManager = game:GetService("VirtualInputManager")
local UserInputService = game:GetService("UserInputService")

local Player = Players.LocalPlayer
local Character = Player.Character or Player.CharacterAdded:Wait()
local RootPart = Character:WaitForChild("HumanoidRootPart")

-- // CONFIGURATION //
local CONFIG = {
	Enabled = true,
	ShowVisuals = true, 
	
	-- KEYS
	HoldKey = Enum.KeyCode.G,    -- Must hold this to active
	AbilityKey = Enum.KeyCode.Q, -- The Block/Slide key
	JumpKey = Enum.KeyCode.Space, -- The Jump key
	
	-- SETTINGS
	BlockRadius = 20,       -- How far sideways/up you can reach (Studs)
	ReactionTime = 0.2,     -- How fast to react
	
	-- HEIGHT LOGIC
	JumpHeightThreshold = 13, -- If ball is higher than this, we Jump + T
	MaxBlockHeight = 30,      -- Don't block if it's way over your head
	
	-- PHYSICS
	MinBallVelocity = 90,      
	BallRadius = 1.0,
	BounceElasticity = 0.7,
	Gravity = Vector3.new(0, -workspace.Gravity, 0),
}

-- // STATE //
local BlockCooldown = false

-- // VISUALS //
local VisContainer = Instance.new("Folder", Workspace)
VisContainer.Name = "CB_Block_System"

local function DrawPoint(pos, col, size)
	if not CONFIG.ShowVisuals then return end
	local p = Instance.new("Part")
	p.Anchored, p.CanCollide, p.CastShadow = true, false, false
	p.Shape, p.Material = "Ball", "Neon"
	p.Size = Vector3.new(size, size, size)
	p.Position = pos
	p.Color = col
	p.Parent = VisContainer
	game.Debris:AddItem(p, 0.1) 
end

-- // INPUT SYSTEM //
local function PerformBlock(InterceptPosition, isHighBall)
	if BlockCooldown then return end
	BlockCooldown = true
	
	task.spawn(function()
		if isHighBall then
			-- == JUMP BLOCK ==
			VirtualInputManager:SendKeyEvent(true, CONFIG.JumpKey, false, game)
			task.wait(0.05) -- Tiny delay to get off ground
			VirtualInputManager:SendKeyEvent(true, CONFIG.AbilityKey, false, game)
			
			task.wait(0.1)
			VirtualInputManager:SendKeyEvent(false, CONFIG.AbilityKey, false, game)
			VirtualInputManager:SendKeyEvent(false, CONFIG.JumpKey, false, game)
		else
			-- == GROUND BLOCK ==
			VirtualInputManager:SendKeyEvent(true, CONFIG.AbilityKey, false, game)
			task.wait(0.05)
			VirtualInputManager:SendKeyEvent(false, CONFIG.AbilityKey, false, game)
		end
		
		task.wait(1.0) 
		BlockCooldown = false
	end)
end

-- // MAIN PHYSICS LOOP //
local function Update(dt)
	-- CHECK 1: Is Q held down?
	if not UserInputService:IsKeyDown(CONFIG.HoldKey) then return end
	if not CONFIG.Enabled or not RootPart then return end

	-- Find Ball
	local Ball = Workspace:FindFirstChild("Temp") and Workspace.Temp:FindFirstChild("Ball")
	if not Ball then Ball = Workspace:FindFirstChild("Ball") end 
	if not Ball then return end
	
	local currentVel = Ball.AssemblyLinearVelocity
	if currentVel.Magnitude < CONFIG.MinBallVelocity then return end

	-- Curve Logic
	local externalAcc = Vector3.zero
	local mfObj = Ball:FindFirstChildWhichIsA("VectorForce", true)
	if mfObj and mfObj.Enabled then
		local rawForce = mfObj.Force
		if mfObj.RelativeTo == Enum.ActuatorRelativeTo.Attachment0 and mfObj.Attachment0 then
			rawForce = mfObj.Attachment0.WorldCFrame:VectorToWorldSpace(rawForce)
		elseif mfObj.RelativeTo == Enum.ActuatorRelativeTo.Attachment1 and mfObj.Attachment1 then
			rawForce = mfObj.Attachment1.WorldCFrame:VectorToWorldSpace(rawForce)
		end
		externalAcc = rawForce / Ball.AssemblyMass
	end

	local simPos = Ball.Position
	local simVel = currentVel
	local stepDt = 0.015 
	
	-- Store Player Position info
	local rootCF = RootPart.CFrame
	local startRelPos = rootCF:PointToObjectSpace(simPos)
	local lastRelZ = startRelPos.Z -- Used to detect when ball crosses our plane
	
	-- PREDICTION LOOP
	for i = 1, 60 do 
		local oldPos = simPos
		
		-- Physics Step
		simVel = simVel + ((CONFIG.Gravity + externalAcc) * stepDt)
		simPos = simPos + (simVel * stepDt)
		
		-- Floor Bounce
		if simPos.Y < CONFIG.BallRadius then
			simPos = Vector3.new(simPos.X, CONFIG.BallRadius, simPos.Z)
			simVel = Vector3.new(simVel.X, -simVel.Y * CONFIG.BounceElasticity, simVel.Z)
		end
		
		-- Visual Trace (Red Line)
		if CONFIG.ShowVisuals and i % 4 == 0 then
			DrawPoint(simPos, Color3.new(1,0,0), 0.2)
		end

		-- == INTERSECTION LOGIC ==
		-- Convert current ball position to Player's Local Space
		local currentRelPos = rootCF:PointToObjectSpace(simPos)
		local currentRelZ = currentRelPos.Z
		
		-- Did the ball cross the Z plane? (Sign change from + to - or vice versa)
		if (lastRelZ * currentRelZ) <= 0 then
			
			-- Calculate Exact Intersection Point (Lerp)
			local totalZDist = math.abs(lastRelZ - currentRelZ)
			local alpha = 0
			if totalZDist > 0.0001 then alpha = math.abs(lastRelZ) / totalZDist end
			
			local exactImpactPos = oldPos:Lerp(simPos, alpha)
			local relImpact = rootCF:PointToObjectSpace(exactImpactPos)
			local impactTime = (i - 1 + alpha) * stepDt
			
			-- 1. REACH CHECK: Is the intersection point within our side/height reach?
			-- (We check if the impact point is close to the root part)
			local distFromCenter = (exactImpactPos - RootPart.Position).Magnitude
			
			if distFromCenter <= CONFIG.BlockRadius then
				
				-- 2. HEIGHT CHECK: Is it reachable vertically?
				if relImpact.Y < CONFIG.MaxBlockHeight then
					
					-- 3. TIMING CHECK
					if impactTime <= CONFIG.ReactionTime then
						
						-- DECIDE JUMP OR GROUND
						local isHighBall = exactImpactPos.Y > CONFIG.JumpHeightThreshold
						
						-- Visuals
						if isHighBall then
							DrawPoint(exactImpactPos, Color3.new(0, 1, 1), 1.0) -- Cyan = Jump
						else
							DrawPoint(exactImpactPos, Color3.new(0, 1, 0), 1.0) -- Green = Ground
						end
						
						PerformBlock(exactImpactPos, isHighBall)
					end
				end
			end
			
			-- Stop predicting once it passes us
			break
		end
		
		lastRelZ = currentRelZ
	end
end

RunService.RenderStepped:Connect(Update)

getgenv().on = true

while on do
if game.Players.LocalPlayer.Character.Status:FindFirstChild("KickCD") then
    game.Players.LocalPlayer.Character.Status:FindFirstChild("KickCD"):Destroy()
end
wait()
end