from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile, Task, TaskBatch, Species, Project, Call, Team

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class UserLoginForm(AuthenticationForm):
    username = forms.CharField(label='Username')
    password = forms.CharField(label='Password', widget=forms.PasswordInput)

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['team', 'is_admin']  # Added team and admin fields
        
    def __init__(self, *args, **kwargs):
        # Get the user making the request
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # If user is not provided or not an admin, hide the is_admin field
        if not user or not user.profile.is_admin:
            self.fields.pop('is_admin', None)
            if 'team' in self.fields:
                self.fields['team'].disabled = True

class TaskBatchForm(forms.ModelForm):
    pickle_file = forms.FileField(
        help_text="Upload a pickle file containing onsets and offsets lists."
    )
    wav_file = forms.FileField(
        help_text="Upload the WAV file for this task batch.",
        required=True
    )
    
    class Meta:
        model = TaskBatch
        fields = ['name', 'species', 'project', 'wav_file']
        # hidden wav_file_name field that will be auto-populated from the wav_file
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set empty label for dropdowns
        self.fields['species'].empty_label = "Select a species"
        self.fields['project'].empty_label = "Select a project"
        
        if user:
            # Get or create user profile
            from .models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Filter species and projects by user's team - always using profile object directly
            if profile.team:
                # Filter querysets
                self.fields['species'].queryset = self.fields['species'].queryset.filter(team=profile.team)
                self.fields['project'].queryset = self.fields['project'].queryset.filter(team=profile.team)

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['wav_file_name', 'onset', 'offset', 'species', 'project', 'status', 
                  'is_done', 'label', 'classification_result', 'confidence', 'notes']
        widgets = {
            'onset': forms.NumberInput(attrs={'step': '0.01'}),
            'offset': forms.NumberInput(attrs={'step': '0.01'}),
            'confidence': forms.NumberInput(attrs={'step': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set empty label for dropdowns
        self.fields['species'].empty_label = "Select a species"
        self.fields['project'].empty_label = "Select a project"
        
        if user:
            # Get or create user profile
            from .models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Filter species and projects by user's team - always using profile object directly
            if profile.team:
                # Filter querysets
                self.fields['species'].queryset = self.fields['species'].queryset.filter(team=profile.team)
                self.fields['project'].queryset = self.fields['project'].queryset.filter(team=profile.team)
        
class TaskUpdateForm(forms.ModelForm):
    """Form for updating task status and labels"""
    class Meta:
        model = Task
        fields = ['status', 'is_done', 'label', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

class SpeciesForm(forms.ModelForm):
    calls_file = forms.FileField(
        required=False,
        help_text="Upload a text file with call types (one per line, format: short_name,long_name)"
    )
    
    class Meta:
        model = Species
        fields = ['name', 'description', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class SpeciesEditForm(forms.ModelForm):
    """Form for editing species without calls file upload"""
    class Meta:
        model = Species
        fields = ['name', 'description', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class CallForm(forms.ModelForm):
    class Meta:
        model = Call
        fields = ['short_name', 'long_name']

class CallFormSet(forms.BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queryset = Call.objects.none()

CallFormSetFactory = forms.modelformset_factory(
    Call, 
    form=CallForm,
    formset=CallFormSet,
    extra=1,
    can_delete=True
)
        
class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
            
class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        
class TeamInvitationForm(forms.Form):
    email = forms.EmailField(
        label='Email Address',
        help_text='Enter the email address of the person you want to invite to your team'
    )