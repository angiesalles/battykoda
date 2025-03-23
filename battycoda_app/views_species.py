import logging
import traceback
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Species, Task, TaskBatch, Call
from .forms import SpeciesForm, SpeciesEditForm, CallFormSetFactory

# Set up logging
logger = logging.getLogger('battycoda.views_species')

@login_required
def species_list_view(request):
    """Display list of species"""
    # Get the user's profile
    profile = request.user.profile
    
    # Filter species by team if the user is in a team
    if profile.team:
        if profile.is_admin:
            # Admin sees all species in their team
            species_list = Species.objects.filter(team=profile.team)
        else:
            # Regular user only sees species in their team
            species_list = Species.objects.filter(team=profile.team)
    else:
        # If no team is assigned, show all species (legacy behavior)
        species_list = Species.objects.all()
    
    context = {
        'species_list': species_list,
    }
    
    return render(request, 'species/species_list.html', context)

@login_required
def species_detail_view(request, species_id):
    """Display detail of a species"""
    species = get_object_or_404(Species, id=species_id)
    
    # Get tasks for this species
    tasks = Task.objects.filter(species=species)
    
    # Get batches for this species
    batches = TaskBatch.objects.filter(species=species)
    
    # Get calls for this species
    calls = Call.objects.filter(species=species)
    
    context = {
        'species': species,
        'tasks': tasks,
        'batches': batches,
        'calls': calls,
    }
    
    return render(request, 'species/species_detail.html', context)

@login_required
def create_species_view(request):
    """Handle creation of a species with image upload and call types"""
    if request.method == 'POST':
        form = SpeciesForm(request.POST, request.FILES)
        call_formset = CallFormSetFactory(request.POST, prefix='calls')
        
        if form.is_valid() and call_formset.is_valid():
            # Save species
            species = form.save(commit=False)
            species.created_by = request.user
            
            # Always set team to user's active team
            species.team = request.user.profile.team
            species.save()
            
            # Keep track of calls created from file
            created_calls = set()
            
            # Note: We no longer process the calls file here.
            # All calls are now handled through the formset.
            
            # Save call types from formset
            for call_form in call_formset:
                if call_form.is_valid() and call_form.cleaned_data and not call_form.cleaned_data.get('DELETE', False):
                    # Check if we have actual data and it's not a duplicate of something from the file
                    short_name = call_form.cleaned_data.get('short_name')
                    if short_name and short_name not in created_calls:
                        call = call_form.save(commit=False)
                        call.species = species
                        call.save()
            
            messages.success(request, 'Species created successfully.')
            return redirect('battycoda_app:species_detail', species_id=species.id)
    else:
        form = SpeciesForm()
        call_formset = CallFormSetFactory(prefix='calls')
    
    context = {
        'form': form,
        'call_formset': call_formset,
    }
    
    return render(request, 'species/create_species.html', context)

@login_required
def edit_species_view(request, species_id):
    """Handle editing of a species"""
    species = get_object_or_404(Species, id=species_id)
    calls = Call.objects.filter(species=species)
    
    if request.method == 'POST':
        form = SpeciesEditForm(request.POST, request.FILES, instance=species)
        call_formset = CallFormSetFactory(request.POST, prefix='calls')
        
        if form.is_valid() and call_formset.is_valid():
            # Save species
            form.save()
            
            # Keep track of calls that should not be deleted
            preserved_calls = set()
            
            # Note: We no longer process the calls file here.
            # All calls are now handled through the formset.
            
            # Save call types from formset
            for call_form in call_formset:
                if call_form.is_valid() and call_form.cleaned_data:
                    if call_form.cleaned_data.get('DELETE', False):
                        # Delete existing call if it has an ID and is marked for deletion
                        if call_form.cleaned_data.get('id'):
                            call_id = call_form.cleaned_data['id'].id
                            if call_id not in preserved_calls:
                                call_form.cleaned_data['id'].delete()
                    elif call_form.cleaned_data.get('short_name'):
                        # Create or update call
                        call = call_form.save(commit=False)
                        call.species = species
                        call.save()
                        preserved_calls.add(call.id)
            
            # Delete any calls not in the preserved set
            if preserved_calls:
                Call.objects.filter(species=species).exclude(id__in=preserved_calls).delete()
            
            messages.success(request, 'Species updated successfully.')
            return redirect('battycoda_app:species_detail', species_id=species.id)
    else:
        form = SpeciesEditForm(instance=species)
        
        # Initialize formset with existing calls
        call_formset = CallFormSetFactory(
            queryset=calls,
            prefix='calls'
        )
    
    context = {
        'form': form,
        'species': species,
        'call_formset': call_formset,
    }
    
    return render(request, 'species/edit_species.html', context)
    
@login_required
@require_POST
def parse_calls_file_view(request):
    """Parse a calls file and return the extracted call types as JSON.
    This endpoint is called asynchronously when a user selects a file to upload.
    It parses the file and returns the call types so they can be added to the form
    before the main form is submitted."""
    if 'calls_file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'No file provided'
        })
    
    calls_file = request.FILES['calls_file']
    logger.info(f"Parsing calls file: {calls_file.name}, size: {calls_file.size}")
    
    try:
        # Read the content of the file
        file_content = calls_file.read().decode('utf-8')
        logger.info(f"File content length: {len(file_content)}")
        
        # Parse the content and extract call types
        calls = []
        lines_processed = 0
        
        # Process each line
        for line in file_content.splitlines():
            lines_processed += 1
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            if ',' in line:
                short_name, long_name = line.split(',', 1)
            elif '|' in line:
                short_name, long_name = line.split('|', 1)
            elif '\t' in line:
                short_name, long_name = line.split('\t', 1)
            else:
                # If no separator, use whole line as short_name and leave long_name empty
                short_name = line
                long_name = ""
                
            short_name = short_name.strip()
            long_name = long_name.strip()
            
            # Add to calls list
            calls.append({
                'short_name': short_name,
                'long_name': long_name
            })
        
        logger.info(f"Parsed {lines_processed} lines, found {len(calls)} valid call types")
        
        # Return JSON response with parsed calls
        return JsonResponse({
            'success': True,
            'calls': calls
        })
        
    except Exception as e:
        logger.error(f"Error parsing calls file: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        })